"""Shared test helpers: an in-memory chain adapter and a transfer builder."""
from engine.chains.tron import Transfer

T0 = 1_700_000_000


class FakeAdapter:
    """Serves transfers from memory, like TronAdapter.transfers()."""
    offline = True

    def __init__(self, transfers):
        self.all = transfers
        self.unavailable = {}

    def history_truncated(self, addr):
        return False

    def transfers(self, addr):
        mine = [t for t in self.all if addr in (t.from_addr, t.to_addr)]
        if not mine:
            raise LookupError(addr)
        return sorted(mine, key=lambda t: t.timestamp), "cached"


def tx(src, dst, amount, ts=T0, h=None):
    return Transfer(tx_hash=h or f"{src}{dst}{ts}{amount}", from_addr=src, to_addr=dst, amount=amount, timestamp=ts)


# ---- the contract rules every trace must satisfy (CONTRACT.md section 4), whatever wallet it came from
def assert_trace_invariants(t):
    import typing

    from contract.schemas import CONTRACT_VERSION, Chain, EdgeType, Method, NodeType, RiskLevel, Source, Typology, TraceResponse
    TraceResponse(**t.model_dump())
    assert t.contract_version == CONTRACT_VERSION and t.source in typing.get_args(Source) and isinstance(t.generated_at, int)
    assert t.notes is None or (isinstance(t.notes, str) and t.notes)
    assert t.risk is None and t.risk_score is None and t.typology in typing.get_args(Typology)

    nodes = {n.id: n for n in t.graph.nodes}
    assert len(nodes) == len(t.graph.nodes), "node ids must be unique"
    roots = [n for n in t.graph.nodes if n.hop == 0]
    assert len(roots) == 1 and roots[0].id == t.wallet and roots[0].type == "scam_wallet" and roots[0].risk is None
    for n in t.graph.nodes:
        assert n.type in typing.get_args(NodeType) and n.chain in typing.get_args(Chain) and n.hop >= -1
        assert (n.hop == -1) == (n.type == "victim")
        assert n.idle_balance >= 0 and isinstance(n.reasons, list) and n.typology in typing.get_args(Typology)
        if n.hop >= 1 and n.chain == "tron":                      # every downstream wallet is scored, with reasons
            assert n.risk in typing.get_args(RiskLevel) and 0.0 <= n.risk_score <= 1.0 and n.reasons, n.id
        if n.risk == "Low":
            assert n.typology == "unknown"                         # only risky wallets carry a scam type
    for e in t.graph.edges:
        assert e.source in nodes and e.target in nodes, "every edge points at real nodes"
        assert e.edge_type in typing.get_args(EdgeType) and isinstance(e.amount, float) and e.amount >= 0
        assert 10 ** 9 < e.timestamp < 4 * 10 ** 9, "timestamps are epoch seconds"
        assert nodes[e.target].hop <= nodes[e.source].hop + 1, "hops grow by at most one along an edge"

    s = t.summary
    assert s.nodes == len(nodes) and s.hops == max((n.hop for n in nodes.values() if n.hop >= 0), default=0)
    assert abs(s.idle_funds - sum(n.idle_balance for n in nodes.values())) < 1e-6
    assert s.total_traced == round(sum(e.amount for e in t.graph.edges if e.source == t.wallet), 2)

    v = t.nearest_vasp
    if v:
        dep = nodes[v.deposit_address]                              # the deposit address exists in the graph
        assert v.evidence and all(isinstance(x, str) and x for x in v.evidence)
        assert 0.0 <= v.confidence <= 1.0 and v.method in typing.get_args(Method) and v.hops == dep.hop
        if v.method == "heuristic":
            assert v.confidence < 0.90
        assert (dep.type == "exchange" or dep.hop == 0) and s.time_to_attribution_sec is not None   # hop 0: the reported wallet IS the exchange
