"""
Recommended next actions for a case (Person B). Runs on top of the engine's output and
replaces whatever recommendations the trace came with.

Rules, in priority order:
  idle funds > 0                 -> urgent  "Act on idle funds"
  nearest VASP, confidence >= 0.6 -> high   "Issue freeze and KYC request to {vasp}"
  nearest VASP, confidence < 0.6  -> normal "Corroborate attribution to {vasp}"
  a bridge reached               -> high    "Continue trace on {destination chain}"
  a mixer reached                -> normal  "Preserve mixer evidence"
  no VASP found                  -> normal  "Monitor wallet; re-trace on movement"

Case urgency (CONTRACT.md section 4, first match wins; thresholds are demo placeholders):
  act_now   idle funds; funds at a VASP deposit address not yet swept; last outgoing tx under 24 h ago
  act_soon  VASP identified at confidence >= 0.70; amount lost >= 10,000; 2+ other linked complaints
  preserve  everything else
"""
import time
from typing import List, Optional, Tuple

from contract.schemas import Node, Recommendation, TraceResponse

FREEZE_MIN_CONFIDENCE = 0.6
CHAIN_NAMES = {"tron": "TRON", "ethereum": "Ethereum", "bsc": "BSC", "polygon": "Polygon",
               "bitcoin": "Bitcoin", "solana": "Solana"}
_ORDER = {"urgent": 0, "high": 1, "normal": 2}

RECENT_SECONDS = 24 * 3600
ACT_SOON_CONFIDENCE = 0.70
ACT_SOON_AMOUNT = 10_000
ACT_SOON_LINKED = 2


def amount(x: float) -> str:
    """7850.0 -> '7,850'; 12.5 -> '12.50'."""
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.2f}"


def describe(node: Node) -> str:
    """How a wallet reads inside a sentence: 'the reported wallet', 'the Ethereum-side wallet'."""
    if node.hop == 0:
        return "the reported wallet"
    if node.label:
        return "the " + node.label.split(" (")[0]
    return f"wallet {node.id[:8]}..."


def build_recommendations(trace: TraceResponse) -> List[Recommendation]:
    nodes = {n.id: n for n in trace.graph.nodes}
    edges = trace.graph.edges
    recs: List[Recommendation] = []

    idle = sorted((n for n in nodes.values() if n.idle_balance > 0), key=lambda n: -n.idle_balance)
    if idle:
        total = sum(n.idle_balance for n in idle)
        where = describe(idle[0]) if len(idle) == 1 else f"{len(idle)} wallets, most in {describe(idle[0])}"
        recs.append(Recommendation(
            priority="urgent", action="Act on idle funds",
            detail=f"{amount(total)} USDT is sitting in {where}. Request a hold from the stablecoin "
                   f"issuer or the next VASP before it moves."))

    v = trace.nearest_vasp
    if v and v.confidence >= FREEZE_MIN_CONFIDENCE:
        recs.append(Recommendation(
            priority="high", action=f"Issue freeze and KYC request to {v.vasp}",
            detail=f"Deposit address received {amount(v.amount)} USDT. Request freeze plus preservation "
                   f"of KYC, linked bank/UPI, phone and IP data."))
    elif v:
        recs.append(Recommendation(
            priority="normal", action=f"Corroborate attribution to {v.vasp}",
            detail=f"Only {v.confidence:.0%} confidence ({v.method}). Confirm the deposit address with "
                   f"more evidence before sending a freeze request."))

    for bridge in (n for n in nodes.values() if n.type == "bridge"):
        out = [nodes[e.target] for e in edges if e.source == bridge.id and e.target in nodes]
        far = next((n for n in out if n.chain != bridge.chain), out[0] if out else None)
        chain = CHAIN_NAMES.get(far.chain, far.chain) if far and far.chain != bridge.chain else "the destination chain"
        follow = describe(far) if far else "the bridge's destination wallet"
        recs.append(Recommendation(
            priority="high", action=f"Continue trace on {chain}",
            detail=f"Funds crossed a bridge. Follow {follow} for onward movement."))

    mixers = {n.id for n in nodes.values() if n.type == "mixer"}
    if mixers:
        mixed = sum(e.amount for e in edges if e.target in mixers)
        recs.append(Recommendation(
            priority="normal", action="Preserve mixer evidence",
            detail=f"{amount(mixed)} USDT entered a mixer. Exit cannot be traced reliably; record the "
                   f"transaction and monitor."))

    if not v:
        recs.append(Recommendation(
            priority="normal", action="Monitor wallet; re-trace on movement",
            detail=f"No exchange reached yet. Watch {trace.wallet} and any wallet still holding funds, "
                   f"and re-run the trace when they move."))

    return sorted(recs, key=lambda r: _ORDER[r.priority])  # stable: rule order within a priority


def build_urgency(trace: TraceResponse, linked_complaints: int = 0,
                  now: Optional[float] = None) -> Tuple[str, List[str]]:
    """(urgency, reasons): the first tier with a firing trigger wins, and every trigger of that tier is listed.

    `linked_complaints` is the number of OTHER complaints in this case's network."""
    now = time.time() if now is None else now
    edges, v = trace.graph.edges, trace.nearest_vasp
    victims = {n.id for n in trace.graph.nodes if n.type == "victim"}
    now_reasons: List[str] = []
    if trace.summary.idle_funds > 0:
        now_reasons.append(f"{amount(trace.summary.idle_funds)} USDT idle in a wallet")
    if v and not any(e.source == v.deposit_address for e in edges):
        now_reasons.append(f"Funds sit at the {v.vasp} deposit address and have not been swept")
    moves = [e.timestamp for e in edges if e.source not in victims]
    if moves and now - max(moves) < RECENT_SECONDS:
        now_reasons.append("Last outgoing transaction was under 24 hours ago")
    if now_reasons:
        return "act_now", now_reasons

    soon_reasons: List[str] = []
    if v and v.confidence >= ACT_SOON_CONFIDENCE:
        soon_reasons.append(f"{v.vasp} identified at {v.confidence:.0%} confidence; funds already swept to its hot wallet")
    if (trace.amount_lost or 0) >= ACT_SOON_AMOUNT:
        soon_reasons.append(f"Amount lost is {amount(trace.amount_lost)} USDT")
    if linked_complaints >= ACT_SOON_LINKED:
        soon_reasons.append(f"Linked to {linked_complaints} other complaints")
    if soon_reasons:
        return "act_soon", soon_reasons

    return "preserve", ["No idle funds or identified exchange; preserve evidence and monitor"]


def with_recommendations(trace: TraceResponse, linked_complaints: int = 0,
                         now: Optional[float] = None) -> TraceResponse:
    urgency, reasons = build_urgency(trace, linked_complaints, now)
    return trace.model_copy(update={"recommendations": build_recommendations(trace),
                                    "urgency": urgency, "urgency_reasons": reasons})
