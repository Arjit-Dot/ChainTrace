"""
The identifier ledger and the leads rules (Person B, investigation stage 4.1).

A case keeps a ledger of IDENTIFIERS (wallets, bank accounts, UPI IDs, phones, handles, domains, apps). From each one
the rules below suggest a LEAD: the institution that holds the identity behind it, what it can tell us, and the
requests to send. Leads are computed from the ledger, never stored, so they always match the rules.

Where identifiers come from: the complaint (the lure channels and where the victim paid), the trace (the reported
wallet, suspected mule wallets, the exchange deposit address, wallets still holding funds), a reply from an
institution (stage 4.3) and an officer typing one in. Nothing here contacts anyone: a lead is a suggestion.
Every score is a suspicion, not a finding; people who hold mule accounts are often victims themselves.
"""
import re
import time
from typing import Dict, List, Optional

from contract.schemas import Complaint, Identifier, IdentifierRequest, Lead, TraceResponse
from product import store

# Placeholders for what the identifier means for the case (how much weight to give it).
COMPLAINT_CONFIDENCE = 0.5       # reported by the victim, not yet checked
REPORTED_WALLET_CONFIDENCE = 0.9
PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2}

# The first four letters of an IFSC code name the bank.
BANKS = {
    "SBIN": "State Bank of India", "HDFC": "HDFC Bank", "ICIC": "ICICI Bank", "UTIB": "Axis Bank", "PUNB": "Punjab National Bank",
    "KKBK": "Kotak Mahindra Bank", "BARB": "Bank of Baroda", "CNRB": "Canara Bank", "UBIN": "Union Bank of India",
    "IDIB": "Indian Bank", "YESB": "Yes Bank", "INDB": "IndusInd Bank", "IBKL": "IDBI Bank", "FDRL": "Federal Bank",
}
# A UPI handle's suffix often shows the app. These are hints, so the lead says "likely".
UPI_APPS = {"ybl": "PhonePe", "paytm": "Paytm", "okaxis": "Google Pay", "okhdfcbank": "Google Pay", "okicici": "Google Pay",
            "oksbi": "Google Pay", "apl": "Amazon Pay"}
PLATFORMS = {"telegram": "Telegram", "whatsapp": "WhatsApp", "instagram": "Instagram", "facebook": "Facebook", "x": "X", "other": "the platform"}


# ---------- normalising, so the same thing is never listed twice ----------
def normalize(kind: str, value: str) -> str:
    v = (value or "").strip()
    if kind == "wallet":
        return v.lower() if v.lower().startswith("0x") else v
    if kind == "bank_account":
        v = re.sub(r"\D", "", v)
    elif kind == "phone":
        v = re.sub(r"\D", "", v)
        v = v[-10:] if len(v) >= 10 else v
    elif kind in ("upi_id", "email", "device", "ip_address"):
        v = v.lower()
    elif kind == "domain":
        v = re.sub(r"^[a-z][a-z0-9+.-]*://", "", v.lower())
        v = re.sub(r"^www\.", "", v.split("/")[0].split("?")[0].split(":")[0])
    elif kind == "social_handle":
        v = v.lower().lstrip("@").strip()
    elif kind == "app":
        v = re.sub(r"\s+", " ", v)
    if not v:
        raise ValueError(f"empty {kind}")
    return v


def bank_of(ifsc: Optional[str]) -> Optional[str]:
    return BANKS.get((ifsc or "")[:4].upper())


def upi_app(upi: str) -> Optional[str]:
    return UPI_APPS.get(upi.rsplit("@", 1)[-1].lower())


# ---------- building the ledger ----------
def _ident(case_id: str, n: int, kind: str, value: str, role: str, source: str, ref: Optional[str], confidence: float,
           label: Optional[str], now: int) -> Identifier:
    return Identifier(identifier_id=f"I-{case_id}-{n:03d}", case_id=case_id, kind=kind, value=normalize(kind, value), label=label,
                      role=role, source=source, source_ref=ref, confidence=round(confidence, 2), added_at=now)


def from_complaint(case_id: str, c: Complaint, now: int) -> List[dict]:
    """(kind, value, role, source, ref, confidence, label) for everything the victim reported."""
    out = [("wallet", c.wallet, "reported", "complaint", c.complaint_id, REPORTED_WALLET_CONFIDENCE, "Reported wallet")]
    if c.scammer_phone:
        out.append(("phone", c.scammer_phone, "lure", "complaint", c.complaint_id, COMPLAINT_CONFIDENCE, "Scammer's phone"))
    if c.scammer_handle:
        platform = PLATFORMS.get(c.scammer_handle_platform or "other")
        out.append(("social_handle", c.scammer_handle, "lure", "complaint", c.complaint_id, COMPLAINT_CONFIDENCE, platform))
    if c.scam_website:
        out.append(("domain", c.scam_website, "lure", "complaint", c.complaint_id, COMPLAINT_CONFIDENCE, "Scam website"))
    if c.scam_app:
        out.append(("app", c.scam_app, "lure", "complaint", c.complaint_id, COMPLAINT_CONFIDENCE, "Scam app"))
    if c.paid_to_upi:
        out.append(("upi_id", c.paid_to_upi, "payment", "complaint", c.complaint_id, COMPLAINT_CONFIDENCE, upi_app(c.paid_to_upi)))
    if c.paid_to_bank_account:
        out.append(("bank_account", c.paid_to_bank_account, "payment", "complaint", c.complaint_id, COMPLAINT_CONFIDENCE,
                    bank_of(c.paid_to_ifsc) or (f"IFSC {c.paid_to_ifsc.upper()}" if c.paid_to_ifsc else None)))
    return out


def from_trace(t: TraceResponse) -> List[tuple]:
    """Suspected mules, the exchange deposit address, and wallets still holding funds (the reported wallet comes from the complaint)."""
    out = []
    for n in t.graph.nodes:
        if n.hop < 1 or n.chain != "tron":
            continue
        holding = n.idle_balance > 0
        if t.nearest_vasp and n.id == t.nearest_vasp.deposit_address:
            role, conf, label = "vasp_deposit", t.nearest_vasp.confidence, t.nearest_vasp.vasp
        elif n.risk in ("High", "Critical") and n.type in ("intermediary", "unknown"):
            role, conf, label = "mule_suspect", n.risk_score or 0.5, "Suspected mule wallet"
        elif holding:
            role, conf, label = "other", 0.9, "Holding funds"
        else:
            continue
        if holding and role != "other":
            label += " (holding funds)"
        out.append(("wallet", n.id, role, "trace", t.case_id, conf, label))
    return out


def build(case_id: str, now: Optional[int] = None) -> int:
    """Fill the case's ledger from its complaint and trace. Safe to run again: duplicates are skipped. Returns how many were added."""
    trace = store.get_trace(case_id)
    if trace is None:
        return 0
    now = int(time.time()) if now is None else now
    complaint = store.get_complaint(trace.complaint_id)
    rows = from_complaint(case_id, complaint, now) if complaint else [("wallet", trace.wallet, "reported", "complaint", trace.complaint_id,
                                                                       REPORTED_WALLET_CONFIDENCE, "Reported wallet")]
    rows += from_trace(trace)
    added = 0
    for kind, value, role, source, ref, conf, label in rows:
        if add(case_id, kind, value, role, source, ref, conf, label, now):
            added += 1
    return added


def add(case_id: str, kind: str, value: str, role: str, source: str, ref: Optional[str], confidence: float,
        label: Optional[str], now: Optional[int] = None) -> Optional[Identifier]:
    """Add one identifier. None if the case already has it."""
    now = int(time.time()) if now is None else now
    value = normalize(kind, value)
    return store.add_identifier(case_id, kind, value, lambda n: _ident(case_id, n, kind, value, role, source, ref, confidence, label, now))


def add_by_officer(case_id: str, req: IdentifierRequest) -> Optional[Identifier]:
    return add(case_id, req.kind, req.value, req.role, "officer", None, 0.5, req.label)


def ensure_all() -> int:
    """Give every case that has no ledger one (the seeded cases, at start-up). Returns how many cases were filled."""
    filled = 0
    for c in store.list_cases():
        if not store.list_identifiers(c.case_id):
            filled += bool(build(c.case_id))
    return filled


# ---------- the leads rules ----------
def _lead(case_id: str, i: Identifier, choke_point: str, holder: str, what: str, requests: List[str], priority: str, why: str) -> Lead:
    return Lead(lead_id=f"L-{i.identifier_id}-{choke_point}", case_id=case_id, identifier_id=i.identifier_id, choke_point=choke_point,
                holder=holder, what_it_identifies=what, requests=requests, priority=priority, rationale=why)


def leads_for(i: Identifier, trace: TraceResponse) -> List[Lead]:
    c = i.case_id
    idle = {n.id: n.idle_balance for n in trace.graph.nodes}
    out: List[Lead] = []
    if i.kind == "wallet":
        if i.role == "vasp_deposit":
            vasp = i.label.split(" (")[0] if i.label else "the exchange"
            out.append(_lead(c, i, "exchange", vasp, "Verified identity, linked bank accounts, login IPs and devices of the account holder",
                             ["kyc_request", "freeze_request", "preservation_notice"], "urgent" if trace.urgency == "act_now" else "high",
                             f"Funds reached an account at {vasp}: it holds the customer's KYC records."))
        if idle.get(i.value, 0) > 0:
            out.append(_lead(c, i, "issuer", "Token issuer (for USDT, Tether)", "No identity: the issuer can freeze the tokens where they sit",
                             ["issuer_hold", "preservation_notice"], "urgent",
                             f"{idle[i.value]:,.0f} USDT is still in this wallet: a hold stops it moving."))
    elif i.kind == "bank_account":
        bank = i.label if i.label and not i.label.startswith("IFSC") else "Bank (to be identified from the IFSC code)"
        out.append(_lead(c, i, "bank", bank, "Account holder, KYC documents, linked mobile, statements and the accounts money moved on to",
                         ["account_details_request", "freeze_request", "preservation_notice"], "urgent",
                         "The victim paid into this account: a prompt freeze can stop the money moving on."))
    elif i.kind == "upi_id":
        app = f"Likely {i.label} (from the handle)" if i.label else "Payment app and the bank behind the handle"
        out.append(_lead(c, i, "payment_app", app, "Registered name, linked bank account and mobile number, device and login records",
                         ["account_details_request", "preservation_notice"], "high", "The victim paid to this UPI ID."))
    elif i.kind == "phone":
        out.append(_lead(c, i, "telecom", "Telecom operator (identify it from the number series)",
                         "SIM subscriber details and ID documents, call and SMS records, handset and location records",
                         ["subscriber_request", "preservation_notice"], "high", "The scammer used this number."))
        out.append(_lead(c, i, "messaging_platform", "Messaging apps registered on this number",
                         "Account registration details and the devices and IPs the account was used from",
                         ["platform_data_request"], "normal", "A phone number is usually also an account on messaging apps."))
    elif i.kind == "social_handle":
        platform = i.label or "the platform"
        out.append(_lead(c, i, "messaging_platform", platform, "Registration details, linked phone and email, IPs and devices the account was used from",
                         ["preservation_notice", "platform_data_request", "takedown_request"], "high",
                         "Accounts like this are deleted quickly: send a preservation notice first."))
    elif i.kind == "domain":
        out.append(_lead(c, i, "domain_host", "Domain registrar and hosting provider", "Registrant and billing details, hosting account, payment trail",
                         ["preservation_notice", "registrant_request", "takedown_request"], "high", "The scam site is run from this domain."))
    elif i.kind == "app":
        out.append(_lead(c, i, "app_store", "App store or distribution platform", "Developer account, contact and payment details",
                         ["preservation_notice", "developer_request", "takedown_request"], "normal", "The victim was asked to install this app."))
    return out


def leads(case_id: str) -> List[Lead]:
    trace = store.get_trace(case_id)
    if trace is None:
        return []
    out = [lead for i in store.list_identifiers(case_id) for lead in leads_for(i, trace)]
    return sorted(out, key=lambda l: (PRIORITY_ORDER[l.priority], l.choke_point, l.identifier_id))
