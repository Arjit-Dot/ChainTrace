"""
Tracing engine (Step 4): follow money forward from the reported wallet and stop at meaningful endpoints.

Best-first search (largest, then most recent, transfer first). Stops at labeled exchange / bridge / mixer
addresses, at depth 5, and for flows under 1% of the case value. Risk fields are placeholders until A6;
attribution (`nearest_vasp`) is A5.
"""
import csv
import heapq
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from contract.schemas import Edge, Graph, Node, TraceRequest, TraceResponse, TraceSummary
from engine.chains.tron import Transfer, TronAdapter
from paths import LABELS_CSV


STOP_TYPES = {"exchange", "bridge", "mixer"}
EDGE_TYPES = {"bridge": "bridge", "mixer": "mixer_in"}
MAX_DEPTH = 5
MIN_SHARE = 0.01          # ignore flows under 1% of the case value
PASS_THROUGH_RATIO = 0.90
PASS_THROUGH_WINDOW = 3600  # seconds


def load_labels(path: Path = LABELS_CSV) -> Dict[str, Tuple[str, str]]:
    """address -> (entity, type) for every labeled address whose type the graph understands."""
    out: Dict[str, Tuple[str, str]] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["type"] in STOP_TYPES:
                out[row["address"]] = (row["entity"], row["type"])
    return out


def is_pass_through(transfers: List[Transfer], addr: str, arrival_ts: int, arrived: float) -> bool:
    """True if `addr` forwards >= 90% of `arrived` within an hour of `arrival_ts`."""
    if arrived <= 0:
        return False
    sent = sum(t.amount for t in transfers
               if t.from_addr == addr and arrival_ts <= t.timestamp <= arrival_ts + PASS_THROUGH_WINDOW)
    return sent >= PASS_THROUGH_RATIO * arrived


def idle_balance(transfers: List[Transfer], addr: str) -> float:
    """Funds still sitting at `addr`: everything received minus everything sent (never negative)."""
    net = sum(t.amount for t in transfers if t.to_addr == addr) - sum(t.amount for t in transfers if t.from_addr == addr)
    return round(max(net, 0.0), 2)


def trace(wallet: str, adapter: TronAdapter, case_value: Optional[float] = None,
          max_depth: int = MAX_DEPTH, min_share: float = MIN_SHARE,
          labels: Optional[Dict[str, Tuple[str, str]]] = None) -> Graph:
    labels = load_labels() if labels is None else labels

    def history(addr: str) -> List[Transfer]:
        try:
            return adapter.transfers(addr)[0]
        except (LookupError, ValueError):  # uncached offline or not a TRON address: no history, do not crash
            return []

    root_hist = history(wallet)
    if case_value is None:
        case_value = sum(t.amount for t in root_hist if t.to_addr == wallet)
    floor = min_share * case_value

    nodes: Dict[str, Node] = {}
    edges: Dict[str, Edge] = {}
    arrival: Dict[str, Tuple[int, float]] = {wallet: (0, 0.0)}  # addr -> (first arrival ts, amount that arrived)
    expanded = set()

    def add_edge(t: Transfer, target_type: Optional[str]):
        key = f"{t.tx_hash}:{t.from_addr}:{t.to_addr}"
        edges.setdefault(key, Edge(source=t.from_addr, target=t.to_addr, tx_hash=t.tx_hash, amount=t.amount,
                                   token=t.token, timestamp=t.timestamp,
                                   edge_type=EDGE_TYPES.get(target_type, "transfer")))

    nodes[wallet] = Node(id=wallet, type="scam_wallet", hop=0, label="Reported", risk=None, risk_score=None)
    for t in root_hist:  # victims: who paid the reported wallet
        if t.to_addr == wallet and t.amount >= floor:
            nodes.setdefault(t.from_addr, Node(id=t.from_addr, type="victim", hop=-1))
            add_edge(t, None)

    counter = 0
    heap: List[tuple] = [(0.0, 0, counter, wallet)]
    while heap:
        _, _, _, addr = heapq.heappop(heap)
        if addr in expanded:
            continue
        expanded.add(addr)
        hop = nodes[addr].hop
        if hop >= max_depth or addr in labels:
            continue
        hist = history(addr)
        since, arrived = arrival[addr]
        outgoing = [t for t in hist if t.from_addr == addr and t.timestamp >= since and t.amount >= floor]
        if addr != wallet and not is_pass_through(hist, addr, since, arrived):
            nodes[addr].type = "unknown"
        elif addr != wallet:
            nodes[addr].type = "intermediary"
        for t in outgoing:
            entity, ltype = labels.get(t.to_addr, (None, None))
            if t.to_addr not in nodes:
                nodes[t.to_addr] = Node(id=t.to_addr, type=ltype or "unknown", label=entity, hop=hop + 1)
                arrival[t.to_addr] = (t.timestamp, t.amount)
                counter += 1
                heapq.heappush(heap, (-t.amount, -t.timestamp, counter, t.to_addr))
            add_edge(t, nodes[t.to_addr].type)

    # leaves that still hold funds get an idle-funds flag
    sources = {e.source for e in edges.values()}
    for addr, node in nodes.items():
        if node.type in ("unknown", "intermediary") and addr not in sources:
            node.idle_balance = idle_balance(history(addr), addr)

    ordered = sorted(nodes.values(), key=lambda n: (n.hop, n.id))
    return Graph(nodes=ordered, edges=sorted(edges.values(), key=lambda e: (e.timestamp, e.tx_hash)))


def summarize(graph: Graph) -> TraceSummary:
    """`total_traced` is what left the reported wallet (matches the hero fixture), not a sum over every hop."""
    downstream = [n for n in graph.nodes if n.hop >= 0]
    root = next((n.id for n in graph.nodes if n.hop == 0), None)
    return TraceSummary(
        hops=max((n.hop for n in downstream), default=0),
        nodes=len(graph.nodes),
        total_traced=round(sum(e.amount for e in graph.edges if e.source == root), 2),
        idle_funds=round(sum(n.idle_balance for n in graph.nodes), 2),
    )


def build_response(req: TraceRequest, adapter: Optional[TronAdapter] = None) -> TraceResponse:
    """Full contract response: downstream risk is a placeholder until A6, the reported wallet and the case have no risk, urgency is B's."""
    adapter = adapter or TronAdapter()
    started = time.time()
    graph = trace(req.wallet, adapter, case_value=req.amount)
    return TraceResponse(
        case_id=f"CASE-{req.complaint_id}", complaint_id=req.complaint_id, wallet=req.wallet, chain="tron",
        fraud_type=req.fraud_type, amount_lost=req.amount, risk=None, risk_score=None,
        graph=graph, summary=summarize(graph), source="cached" if adapter.offline else "live",
        generated_at=int(started),
    )


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.exit("usage: python -m engine.trace.tracing <wallet> [amount]")
    amount = float(argv[1]) if len(argv) > 1 else None
    g = trace(argv[0], TronAdapter(offline=True), case_value=amount)
    for n in g.nodes:
        print(f"hop {n.hop:>2}  {n.type:<12} {n.id}  {n.label or ''}  idle={n.idle_balance}")
    for e in g.edges:
        print(f"  {e.source[:8]} -> {e.target[:8]}  {e.amount:>10}  {e.edge_type}")
    print(summarize(g))


if __name__ == "__main__":
    main()
