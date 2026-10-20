"""
Freeze notice for a case (Person B), rendered from the stored trace with
templates/freeze_notice.txt.j2. Addressed to nearest_vasp.contact (engine output).
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import networkx as nx
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from contract.schemas import CaseSummary, Edge, FreezeNotice, TraceResponse
from recommendations import amount

IST = timezone(timedelta(hours=5, minutes=30), "IST")
REQUESTED_ACTIONS = [
    "Freeze funds",
    "Preserve KYC records",
    "Share linked bank/UPI/phone/IP data",
]

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                   trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)


def ist(ts: int) -> str:
    return datetime.fromtimestamp(ts, IST).strftime("%d %b %Y, %H:%M:%S IST")


def utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%H:%M:%S UTC")


def trail(trace: TraceResponse) -> List[Edge]:
    """Transfers from the reported wallet to the deposit address, then out of the deposit address."""
    deposit = trace.nearest_vasp.deposit_address
    g = nx.DiGraph()
    for e in trace.graph.edges:  # keep the largest transfer between any two wallets
        if not g.has_edge(e.source, e.target) or g[e.source][e.target]["edge"].amount < e.amount:
            g.add_edge(e.source, e.target, edge=e)
    try:
        path = nx.shortest_path(g, trace.wallet, deposit)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        path = []
    inbound = [g[a][b]["edge"] for a, b in zip(path, path[1:])]
    if not inbound:  # no clean path: list every transfer into the deposit address
        inbound = [e for e in trace.graph.edges if e.target == deposit]
    sweeps = [e for e in trace.graph.edges if e.source == deposit]
    return sorted(inbound, key=lambda e: e.timestamp) + sorted(sweeps, key=lambda e: e.timestamp)


def build_freeze_notice(trace: TraceResponse, case: Optional[CaseSummary]) -> FreezeNotice:
    """Raises ValueError when no exchange was identified (nothing to freeze)."""
    v = trace.nearest_vasp
    if v is None:
        raise ValueError("No exchange identified for this case: nothing to freeze.")
    labels = {n.id: n.label for n in trace.graph.nodes}
    lost = case.amount_lost if case else trace.amount_lost
    body = _env.get_template("freeze_notice.txt.j2").render(
        vasp=v, case_id=trace.case_id, complaint_id=trace.complaint_id,
        today=datetime.now(IST).strftime("%d %b %Y"),
        state=case.state if case and case.state != "Unknown" else None,
        fraud_type=(case.fraud_type if case else trace.fraud_type),
        lost=amount(lost) if lost is not None else "an unknown amount of",
        wallet=trace.wallet, chain=trace.chain.upper() if trace.chain == "tron" else trace.chain.title(),
        trail=[{"edge": e, "from_label": labels.get(e.source), "to_label": labels.get(e.target)}
               for e in trail(trace)],
        source=trace.source, amount=amount, ist=ist, utc=utc,
    )
    return FreezeNotice(
        case_id=trace.case_id,
        to_vasp=v.vasp,
        to_email=v.contact,
        subject=f"Request to freeze funds and preserve records, Complaint {trace.complaint_id}",
        body=body,
        requested_actions=REQUESTED_ACTIONS,
        status="sent" if case and case.status == "notice_sent" else "draft",
    )
