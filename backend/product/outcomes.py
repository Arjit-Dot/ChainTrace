"""
Where the money went, and who the suspected mules are (Person B, investigation 4.2).

Each kind of endpoint needs a different response, and this module says which:
  vasp          an exchange: KYC and freeze request. It holds the account holder's identity.
  dex           a swap pool: there is NO account holder and nothing to freeze. Follow the swapped tokens; ask the token
                issuer to hold any USDT still in the flow; preserve the swap as evidence.
  bank_account  an account the victim paid: freeze or lien request to the bank, plus account details.
  mixer         cannot be followed through: preserve the evidence and watch the exits.
  bridge        the money crossed to another chain: continue the trace there.
  idle_wallet   funds still sitting in a wallet: ask the token issuer for a hold, now.
  dead_end      the trace ended without reaching any of these.

Computed from the stored trace and the ledger, never stored. Mules are always "suspected": the person holding a mule
account is often a victim too.
"""
from collections import defaultdict
from typing import Dict, List, Optional

from contract.schemas import Mule, Outcome
from product import ledger, store
from product.recommendations import amount

STATUS_ORDER = {"action_needed": 0, "in_progress": 1, "info": 2}
ONWARD = {"exchange": "vasp", "dex": "dex", "mixer": "mixer", "bridge": "bridge", "bank_account": "bank_account"}


def _lead_ids(leads, choke_point: str, value: str, ident_values: Dict[str, str]) -> List[str]:
    return [l.lead_id for l in leads if l.choke_point == choke_point and ident_values.get(l.identifier_id) == value]


def outcomes(case_id: str) -> List[Outcome]:
    trace, case = store.get_trace(case_id), store.get_case(case_id)
    if trace is None or case is None:
        return []
    nodes = {n.id: n for n in trace.graph.nodes}
    idents = store.list_identifiers(case_id)
    values = {i.identifier_id: i.value for i in idents}
    leads = ledger.leads(case_id)
    inbound: Dict[str, float] = defaultdict(float)
    from_types: Dict[str, set] = defaultdict(set)
    for e in trace.graph.edges:
        inbound[e.target] += e.amount
        from_types[e.target].add(nodes[e.source].type if e.source in nodes else "unknown")
    out: List[Outcome] = []
    n = 0

    def add(kind, title, subject, label, amt, status, handling, lead_ids):
        nonlocal n
        n += 1
        out.append(Outcome(outcome_id=f"O-{case_id}-{n:02d}", case_id=case_id, kind=kind, title=title, subject=subject, subject_label=label,
                           amount=round(amt, 2) if amt else None, status=status, handling=handling, lead_ids=lead_ids))

    sent = case.status == "notice_sent"
    for node in trace.graph.nodes:
        if node.hop < 0:
            continue
        label = node.label
        if node.type == "exchange" and from_types[node.id] <= {"exchange"} and from_types[node.id]:
            continue                                                   # the hot wallet behind a deposit address: one outcome is enough
        if node.type == "exchange" or (trace.nearest_vasp and node.id == trace.nearest_vasp.deposit_address):
            vasp = (label or "the exchange").split(" (")[0]
            add("vasp", f"Funds reached {vasp}", node.id, label, inbound[node.id] or (trace.nearest_vasp.amount if trace.nearest_vasp else None),
                "in_progress" if sent else "action_needed",
                [f"Send the KYC and freeze request to {vasp}" + (" (sent)" if sent else " (the freeze notice is drafted on this case)"),
                 "Ask for the account holder's KYC, linked bank accounts, login IPs and devices",
                 "Record the reply: any bank accounts it lists are mule accounts to freeze, and any phones or emails open new leads"],
                _lead_ids(leads, "exchange", node.id, values))
        elif node.type == "dex":
            add("dex", f"Funds were swapped on {(label or 'a DEX pool').split(' (')[0]}", node.id, label, inbound[node.id], "info",
                ["A DEX pool has no account holder or custodian: it cannot be asked for KYC or told to freeze",
                 "Record the swap and follow the wallet that received the swapped tokens",
                 "Ask the token issuer to hold any USDT still in the flow",
                 "Preserve the swap transaction as evidence"], [])
        elif node.type == "mixer":
            add("mixer", f"Funds entered {(label or 'a mixer').split(' (')[0]}", node.id, label, inbound[node.id], "info",
                ["Funds cannot be followed through a mixer",
                 "Preserve the transactions as evidence and watch the wallets that may receive its output",
                 "Ask whoever fed the mixer (the exchange or wallet service before it) for its records"], [])
        elif node.type == "bridge":
            onward = sorted({nodes[e.target].chain for e in trace.graph.edges if e.source == node.id and e.target in nodes})
            add("bridge", f"Funds crossed {(label or 'a bridge').split(' (')[0]}", node.id, label, inbound[node.id],
                "in_progress" if onward else "action_needed",
                [("The trace continues on " + ", ".join(c.capitalize() for c in onward)) if onward else "Continue the trace on the destination chain",
                 "Ask the bridge operator for its records of the crossing"], [])
        elif node.idle_balance > 0:
            add("idle_wallet", "Funds are still sitting in a wallet", node.id, node.label, node.idle_balance, "action_needed",
                [f"Ask the token issuer to hold the {amount(node.idle_balance)} USDT now, before it moves",
                 "Watch the wallet: any movement re-ranks the case and raises an alert",
                 "If a person or service controls it, the leads panel shows who to ask"],
                _lead_ids(leads, "issuer", node.id, values))
    for i in idents:
        if i.kind == "bank_account":
            bank = i.label if i.label and not i.label.startswith("IFSC") else None
            where = f" at {bank}" if bank else ""
            title = f"The victim paid a bank account{where}" if i.source == "complaint" else f"A suspected mule account{where} appears in a reply"
            add("bank_account", title, i.value, i.label, None, "action_needed",
                [f"Send a freeze or lien request to {bank or 'the bank (identify it from the IFSC code)'}",
                 "Ask for the account holder's KYC, statements and linked mobile number",
                 "Ask the bank to preserve its records, including any cash withdrawal and CCTV",
                 "Trace where money moved on from this account: each onward account may be another mule"],
                _lead_ids(leads, "bank", i.value, {x.identifier_id: x.value for x in idents}))
    if not out:
        add("dead_end", "The trace ended without reaching an exchange, DEX, bank account or mixer", trace.wallet, None, None, "info",
            ["Check the leads panel: the lure channels may point to the people behind this",
             "Watch the wallets that still hold funds: a movement re-ranks the case"], [])
    return sorted(out, key=lambda o: (STATUS_ORDER[o.status], o.outcome_id))


def mules(case_id: str) -> List[Mule]:
    trace = store.get_trace(case_id)
    if trace is None:
        return []
    nodes = {n.id: n for n in trace.graph.nodes}
    idents = store.list_identifiers(case_id)
    wallet_ident = {i.value: i.identifier_id for i in idents if i.kind == "wallet"}
    out: List[Mule] = []
    for n in trace.graph.nodes:
        if n.hop < 1 or n.chain != "tron" or n.type not in ("intermediary", "unknown") or n.risk not in ("High", "Critical"):
            continue
        received = sum(e.amount for e in trace.graph.edges if e.target == n.id)
        sent_edges = [e for e in trace.graph.edges if e.source == n.id]
        onward = sorted({ONWARD.get(nodes[e.target].type, "wallet") for e in sent_edges if e.target in nodes})
        out.append(Mule(case_id=case_id, kind="wallet", value=n.id, label=n.label, hop=n.hop, risk=n.risk, risk_score=n.risk_score,
                        reasons=n.reasons, received=round(received, 2), forwarded=round(sum(e.amount for e in sent_edges), 2),
                        onward=onward, identifier_id=wallet_ident.get(n.id)))
    for i in idents:
        if i.kind == "bank_account":
            out.append(Mule(case_id=case_id, kind="bank_account", value=i.value, label=i.label, reasons=[
                "The victim reported paying into this account", "Not yet checked: the holder may be a victim too"], identifier_id=i.identifier_id))
    return sorted(out, key=lambda m: -m.received)
