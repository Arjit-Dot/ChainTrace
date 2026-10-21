"""
Requests to institutions and their replies (Person B, investigation 4.3).

  lead  ->  DRAFT letter  ->  officer APPROVES  ->  SENT  ->  acknowledged  ->  REPLIED  ->  closed

Nothing is ever transmitted: "send" records that the officer sent it, and the acknowledgement and the reply are
SIMULATED (a demo button). Every letter is a DRAFT for an officer: legal references, names and dates are placeholders.
A letter never contains the victim's name, mobile number or other personal details, only the case reference, the
identifier concerned and the amount. Every reply is FICTIONAL, built from the personas in personas.py, and adds the
identifiers it mentions to the case's ledger, which opens new leads.
"""
import time
from typing import Dict, List, Optional, Tuple

from contract.schemas import InstitutionRequest, Lead, Reply, ReplyField, RequestCreate, RequestEvent
from product import ledger, personas, store
from product.recommendations import amount

ALLOWED_NEXT = {"draft": {"approved"}, "approved": {"sent"}, "sent": {"acknowledged"}, "acknowledged": {"replied"}}
KIND_LABEL = {
    "kyc_request": "KYC and account information request", "account_details_request": "Account details request",
    "freeze_request": "Freeze / hold request", "subscriber_request": "Subscriber details request",
    "platform_data_request": "Platform data request", "registrant_request": "Registrant details request",
    "developer_request": "Developer details request", "takedown_request": "Takedown request",
    "preservation_notice": "Data preservation notice", "issuer_hold": "Token hold request",
}
ASKS = {
    "preservation_notice": ["Preserve ALL records relating to the identifier above (account, logs, messages, IP addresses, devices, "
                            "transactions) from [start date] until further notice. Do not delete or alter them.",
                            "Confirm in writing that the records are preserved."],
    "kyc_request": ["Verified identity of the account holder: full name, ID documents, registered mobile number and email.",
                    "Date the account was opened and any linked bank accounts or UPI IDs.",
                    "Login IP addresses with timestamps, and device identifiers, for [period].",
                    "Transaction history for [period], including the deposit and withdrawal destinations."],
    "freeze_request": ["Place a freeze or hold on the account / balance concerned so that nothing can be withdrawn.",
                       "Confirm the balance held and the reference of the hold."],
    "account_details_request": ["Account holder's name, KYC documents, registered mobile number and email, and branch.",
                                "Date the account was opened, and a statement for [period].",
                                "The accounts and UPI IDs that money moved on to, and any cash withdrawals with their locations."],
    "subscriber_request": ["Subscriber details: name, address, ID documents and date of activation.",
                           "Other numbers on the same ID and the handset identifiers (IMEI) used with this number.",
                           "Call and SMS records for [period], with the tower locations."],
    "platform_data_request": ["Registration details: phone number, email address and sign-up date.",
                              "Sign-in IP addresses with timestamps, and the devices the account was used from.",
                              "Linked accounts and group memberships relevant to the fraud."],
    "registrant_request": ["Registrant and billing details, the registrar, the hosting account and its IP address.",
                           "The payment method used, and the creation and renewal dates."],
    "developer_request": ["Developer account details, contact email and phone, and payment details.",
                          "Versions of the app distributed and the dates."],
    "takedown_request": ["After preserving the data above, remove or suspend the content, account or app used for the fraud.",
                         "Confirm the date and reference of the action."],
    "issuer_hold": ["Place a hold on the tokens at the wallet above so that they cannot move.",
                    "Confirm the amount held and the reference."],
}
IDENT_LABEL = {"wallet": "Wallet", "bank_account": "Bank account", "upi_id": "UPI ID", "phone": "Phone number", "email": "Email",
               "device": "Device", "ip_address": "IP address", "social_handle": "Social media handle", "domain": "Domain", "app": "App"}
STATUS_NOTE = {"approved": "Approved by an officer (demo: no login)", "sent": "Sent (SIMULATED: nothing is actually transmitted)",
               "acknowledged": "Acknowledged by the institution (SIMULATED)", "replied": "Reply received (SIMULATED, fictional data)",
               "closed": "Closed by an officer"}


class Refused(Exception):
    """A request cannot move that way (the route turns this into a 409)."""


# ---------- the letter ----------
def write_letter(req_id: str, lead: Lead, ident, kind: str, case_id: str, complaint_ref: str, amt: Optional[float]) -> Tuple[str, str]:
    title = KIND_LABEL[kind]
    subject = f"{title}: {lead.holder} (ref {complaint_ref})"
    money = f"about {amount(amt)} USDT" if amt else "money"
    what = f"{IDENT_LABEL.get(ident.kind, ident.kind)}: {ident.value}" + (f" ({ident.label})" if ident.label else "")
    asks = "\n".join(f"  {i}. {a}" for i, a in enumerate(ASKS[kind], 1))
    body = f"""DRAFT FOR OFFICER REVIEW. Legal references, names, dates and signatures below are placeholders.

To:        {lead.holder}
From:      [Officer name, designation, unit and address]
Date:      [Date of issue]
Reference: {complaint_ref} / {case_id}   (request {req_id})

Subject:   {title}

[Legal basis: the Act and section under which this request is made, to be inserted by the officer]

1. Background
We are investigating a cyber-financial fraud in which {money} was obtained by deception and passed through
accounts connected to the identifier below.

2. Identifier concerned
  {what}

3. What we ask {lead.holder} to do
{asks}

4. Timeframe
Please respond by [date]. If you cannot respond in full by then, please confirm now that the records are preserved.

5. Contact and confidentiality
[Officer contact details]. Please quote the reference above in your reply.
[Non-disclosure instruction, if applicable under the law cited above]
"""
    return subject, body


# ---------- the workflow ----------
def create(case_id: str, body: RequestCreate) -> Optional[InstitutionRequest]:
    """Turn a lead into a DRAFT request. None if that lead already has one of this kind. Raises Refused for a bad lead or kind."""
    lead = next((l for l in ledger.leads(case_id) if l.lead_id == body.lead_id), None)
    if lead is None:
        raise Refused("That lead does not exist on this case.")
    if body.kind not in lead.requests:
        raise Refused(f"A {KIND_LABEL[body.kind].lower()} is not one of the requests for this lead.")
    ident = next(i for i in store.list_identifiers(case_id) if i.identifier_id == lead.identifier_id)
    trace = store.get_trace(case_id)
    now = int(time.time())

    def make(n: int) -> InstitutionRequest:
        rid = f"R-{case_id}-{n:03d}"
        subject, text = write_letter(rid, lead, ident, body.kind, case_id, trace.complaint_id, trace.amount_lost)
        return InstitutionRequest(request_id=rid, case_id=case_id, lead_id=lead.lead_id, identifier_id=lead.identifier_id,
                                  choke_point=lead.choke_point, holder=lead.holder, kind=body.kind, subject=ident.value, status="draft",
                                  letter_subject=subject, letter_body=text, created_at=now, updated_at=now,
                                  history=[RequestEvent(at=now, status="draft", note="Draft letter generated from a lead")])

    return store.add_request(case_id, lead.lead_id, body.kind, make)


def advance(request_id: str, to: str) -> InstitutionRequest:
    req = store.get_request(request_id)
    if req is None:
        raise LookupError(request_id)
    if to not in ALLOWED_NEXT.get(req.status, set()):
        raise Refused(f"This request is {req.status}: it cannot go to {to}.")
    now = int(time.time())
    extra = {"reference": ledger_ref(req)} if to == "sent" else {}
    return store.update_request(request_id, status=to, updated_at=now, history=req.history + [RequestEvent(at=now, status=to, note=STATUS_NOTE[to])], **extra)


def ledger_ref(req: InstitutionRequest) -> str:
    return personas.fake_ref("SIM", req.request_id)


def close(request_id: str) -> InstitutionRequest:
    req = store.get_request(request_id)
    if req is None:
        raise LookupError(request_id)
    if req.status in ("draft", "approved", "closed"):
        raise Refused(f"This request is {req.status}: only a request that was sent can be closed.")
    now = int(time.time())
    return store.update_request(request_id, status="closed", updated_at=now, history=req.history + [RequestEvent(at=now, status="closed", note=STATUS_NOTE["closed"])])


def simulate_step(request_id: str) -> Tuple[InstitutionRequest, Optional[Reply]]:
    """Demo button: sent -> acknowledged, then acknowledged -> replied (with a fictional reply that adds identifiers)."""
    req = store.get_request(request_id)
    if req is None:
        raise LookupError(request_id)
    if req.status == "sent":
        return advance(request_id, "acknowledged"), None
    if req.status == "acknowledged":
        reply = build_reply(req)
        return advance(request_id, "replied"), reply
    raise Refused(f"This request is {req.status}: there is nothing to simulate.")


# ---------- fictional replies ----------
MAX_BANK_HOPS = 2          # how many accounts deep a bank's reply keeps naming "money moved on to"; after that it left as cash


def bank_depth(req: InstitutionRequest) -> int:
    """1 for an account an exchange named, 2 for the account a bank said money moved on to, and so on."""
    depth, current = 1, req
    for _ in range(MAX_BANK_HOPS + 2):
        ident = next((i for i in store.list_identifiers(current.case_id) if i.identifier_id == current.identifier_id), None)
        origin = store.get_request(ident.source_ref) if ident and ident.source == "reply" and ident.source_ref else None
        if origin is None or origin.choke_point != "bank":
            return depth
        depth, current = depth + 1, origin
    return depth

def build_reply(req: InstitutionRequest) -> Reply:
    case_id, now = req.case_id, int(time.time())
    idents = store.list_identifiers(case_id)
    persona = personas.persona_for([i.value for i in idents], case_id)
    mule = personas.mule_account(f"{case_id}:{req.subject}")
    trace = store.get_trace(case_id)
    held = trace.nearest_vasp.amount if trace and trace.nearest_vasp else trace.summary.idle_funds if trace else 0.0
    ref = personas.fake_ref("REF", req.request_id)
    fields: List[Tuple[str, str]] = []
    new: List[Tuple[str, str, str, str]] = []          # (kind, value, role, label)
    kind, point = req.kind, req.choke_point

    if kind == "preservation_notice":
        summary = f"{req.holder} confirms the records are preserved."
        fields = [("Status", "Records preserved for 180 days"), ("Reference", ref)]
    elif kind in ("freeze_request", "issuer_hold"):
        what = "Tokens held" if kind == "issuer_hold" else "Account frozen"
        summary = f"{req.holder} confirms the hold."
        fields = [("Status", what), ("Amount held", f"{amount(held)} USDT" if held else "As per balance"), ("Reference", ref)]
    elif kind == "takedown_request":
        summary = f"{req.holder} confirms the action."
        fields = [("Status", "Content removed / account suspended"), ("Reference", ref)]
    elif point == "exchange":
        summary = f"{req.holder} supplies the account holder's KYC (fictional)."
        fields = [("Account holder", persona["name"]), ("ID document", persona["doc"]), ("Registered mobile", persona["phone"]),
                  ("Registered email", persona["email"]), ("Account opened", "31 days before the deposit"),
                  ("Linked bank account", f"{mule['bank']} {mule['account']} ({mule['ifsc']})"),
                  ("Recent login IPs", f"{persona['ip']}, {persona['ip2']}"), ("Device", persona["device"])]
        new = [("phone", persona["phone"], "other", "From exchange KYC"), ("email", persona["email"], "other", "From exchange KYC"),
               ("bank_account", mule["account"], "mule_suspect", mule["bank"]), ("ip_address", persona["ip"], "other", "Login IP"),
               ("device", persona["device"], "other", "Registered device")]
    elif point == "bank":
        holder = f"Kiran Pillai (demo {int(mule['account'][-3:]) % 100:02d})"
        onward = personas.mule_account(f"onward:{mule['account']}")
        last = bank_depth(req) >= MAX_BANK_HOPS
        summary = f"{req.holder} supplies the account's details (fictional)."
        fields = [("Account holder", holder), ("ID document", "Aadhaar ending 2040"), ("Registered mobile", persona["alt_phone"]),
                  ("Account opened", "27 days before the first credit"), ("Credits in the period", f"{amount(held or 1000)} USDT equivalent, in few large payments"),
                  ("Money moved on to", "Withdrawn in cash at ATMs (locations to follow)" if last else f"{onward['bank']} {onward['account']}"), ("Reference", ref)]
        new = [("phone", persona["alt_phone"], "other", "Registered on the mule account")]
        if not last:
            new.append(("bank_account", onward["account"], "mule_suspect", onward["bank"]))
    elif point == "payment_app":
        summary = f"{req.holder} supplies the registered details (fictional)."
        fields = [("Registered name", f"Kiran Pillai (demo {int(mule['account'][-3:]) % 100:02d})"), ("Linked bank account", mule["account"]),
                  ("Registered mobile", persona["alt_phone"]), ("Device", persona["device"]), ("Reference", ref)]
        new = [("bank_account", mule["account"], "mule_suspect", mule["bank"]), ("phone", persona["alt_phone"], "other", "Registered on the UPI ID"),
               ("device", persona["device"], "other", "Registered device")]
    elif point == "telecom":
        summary = f"{req.holder} supplies the SIM subscriber's details (fictional)."
        fields = [("Subscriber name", persona["name"]), ("Address", f"[withheld in this demo], {persona['city']}"), ("ID document", persona["doc"]),
                  ("SIM activated", "44 days before the first complaint"), ("Other number on the same ID", persona["alt_phone"]),
                  ("Handset (IMEI)", persona["device"]), ("Reference", ref)]
        new = [("phone", persona["alt_phone"], "other", "Same subscriber"), ("device", persona["device"], "other", "Handset used")]
    elif point == "messaging_platform":
        summary = f"{req.holder} supplies the account's registration data (fictional)."
        fields = [("Registered phone", persona["phone"]), ("Registered email", persona["email"]), ("Account created", "38 days before the first complaint"),
                  ("Sign-in IPs", f"{persona['ip']}, {persona['ip2']}"), ("Device", persona["device"]), ("Reference", ref)]
        new = [("phone", persona["phone"], "other", "Account registration"), ("email", persona["email"], "other", "Account registration"),
               ("ip_address", persona["ip"], "other", "Sign-in IP"), ("device", persona["device"], "other", "Device")]
    elif point == "domain_host":
        summary = f"{req.holder} supplies the registrant details (fictional)."
        fields = [("Registrant", persona["name"]), ("Registrant email", persona["email"]), ("Registrant phone", persona["phone"]),
                  ("Registrar", "Demo Registrar Ltd"), ("Hosting IP", persona["ip"]), ("Payment method", "Card ending 1234"), ("Reference", ref)]
        new = [("email", persona["email"], "other", "Domain registrant"), ("phone", persona["phone"], "other", "Domain registrant"),
               ("ip_address", persona["ip"], "other", "Hosting IP")]
    else:                                              # app_store, p2p_desk and anything else
        summary = f"{req.holder} supplies the developer details (fictional)."
        fields = [("Developer name", persona["name"]), ("Developer email", persona["email"]), ("Payment account", "ending 2210"), ("Reference", ref)]
        new = [("email", persona["email"], "other", "Developer account")]

    added = []
    for k, v, role, label in new:
        got = ledger.add(case_id, k, v, role, "reply", req.request_id, 0.8, label, now)
        if got:
            added.append(got.identifier_id)
    rec = Reply(reply_id=f"P-{req.request_id}", request_id=req.request_id, case_id=case_id, received_at=now, summary=summary,
                fields=[ReplyField(label=a, value=b) for a, b in fields], new_identifier_ids=added, fictional=True)
    store.add_reply(rec)
    return rec


# ---------- demo: run the whole first round at once ----------
PRIMARY = {"exchange": "kyc_request", "bank": "account_details_request", "payment_app": "account_details_request", "telecom": "subscriber_request",
           "messaging_platform": "platform_data_request", "domain_host": "registrant_request", "app_store": "developer_request",
           "issuer": "issuer_hold", "p2p_desk": "kyc_request"}
MAX_ROUNDS = 3


def demo_run(case_id: str, rounds: int = 1) -> Dict[str, int]:
    """DEMO: for every lead without a request, draft the main request, approve, send, and simulate the acknowledgement and
    reply; repeat for the leads those replies open. A shortcut for showing the investigation; everything is simulated."""
    done = {"requests": 0, "replies": 0, "new_identifiers": 0}
    for _ in range(max(1, min(rounds, MAX_ROUNDS))):
        progressed = False
        for lead in ledger.leads(case_id):
            kind = PRIMARY.get(lead.choke_point)
            if kind not in lead.requests:
                continue
            req = create(case_id, RequestCreate(lead_id=lead.lead_id, kind=kind))
            if req is None:
                continue
            for to in ("approved", "sent"):
                advance(req.request_id, to)
            simulate_step(req.request_id)
            _, reply = simulate_step(req.request_id)
            done["requests"] += 1
            done["replies"] += 1
            done["new_identifiers"] += len(reply.new_identifier_ids)
            progressed = True
        if not progressed:
            break
    return done
