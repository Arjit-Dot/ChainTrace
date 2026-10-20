"""Tracing engine (Step 4): stop rules, ordering, cycles, pass-through, idle funds, contract shape, hero case."""
from pathlib import Path

import pytest

from chains.tron import Transfer, TronAdapter
from contract.schemas import Graph, TraceRequest, TraceResponse
from tracing import build_response, idle_balance, is_pass_through, load_labels, summarize, trace

HERO = "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo"
HERO_EXCHANGE = "TJ4imTmNr3FZoqR2jsRBuXS2aNXNAsAXhK"
T0 = 1_700_000_000


class FakeAdapter:
    """Serves transfers from memory, like TronAdapter.transfers()."""
    offline = True

    def __init__(self, transfers):
        self.all = transfers

    def transfers(self, addr):
        mine = [t for t in self.all if addr in (t.from_addr, t.to_addr)]
        if not mine:
            raise LookupError(addr)
        return sorted(mine, key=lambda t: t.timestamp), "cached"


def tx(src, dst, amount, ts=T0, h=None):
    return Transfer(tx_hash=h or f"{src}{dst}{ts}{amount}", from_addr=src, to_addr=dst, amount=amount, timestamp=ts)


def types(g):
    return {n.id: n.type for n in g.nodes}


# ---- labels
def test_load_labels_types():
    labels = load_labels()
    assert labels[HERO_EXCHANGE] == ("Example Exchange A", "exchange")
    assert {t for _, t in labels.values()} <= {"exchange", "bridge", "mixer"}
    assert any(t == "bridge" for _, t in labels.values()) and any(t == "mixer" for _, t in labels.values())


# ---- stop rules
@pytest.mark.parametrize("kind,edge", [("exchange", "transfer"), ("bridge", "bridge"), ("mixer", "mixer_in")])
def test_does_not_expand_past_labeled_endpoint(kind, edge):
    ts = [tx("V", "S", 1000, T0), tx("S", "L", 1000, T0 + 10), tx("L", "X", 1000, T0 + 20)]
    g = trace("S", FakeAdapter(ts), labels={"L": ("Lab", kind)})
    assert types(g)["L"] == kind and "X" not in types(g)
    assert [e.edge_type for e in g.edges if e.target == "L"] == [edge]


def test_stops_at_depth_limit():
    chain = ["S"] + [f"W{i}" for i in range(8)]
    ts = [tx("V", "S", 1000, T0)] + [tx(a, b, 1000, T0 + 10 * i) for i, (a, b) in enumerate(zip(chain, chain[1:]))]
    g = trace("S", FakeAdapter(ts), labels={})
    assert max(n.hop for n in g.nodes) == 5 and "W5" not in types(g)


def test_drops_flows_under_one_percent():
    ts = [tx("V", "S", 10000, T0), tx("S", "BIG", 9900, T0 + 5), tx("S", "DUST", 99, T0 + 6)]
    g = trace("S", FakeAdapter(ts), labels={})
    assert "BIG" in types(g) and "DUST" not in types(g)


def test_ignores_transfers_before_funds_arrived():
    ts = [tx("V", "S", 1000, T0), tx("S", "A", 1000, T0 + 10), tx("A", "OLD", 500, T0 - 999), tx("A", "NEW", 1000, T0 + 20)]
    g = trace("S", FakeAdapter(ts), labels={})
    assert "NEW" in types(g) and "OLD" not in types(g)


# ---- ordering and cycles
def test_best_first_expands_largest_flow_first():
    ts = [tx("V", "S", 10000, T0), tx("S", "SMALL", 2000, T0 + 1), tx("S", "BIG", 8000, T0 + 2),
          tx("SMALL", "SMALL2", 2000, T0 + 3), tx("BIG", "BIG2", 8000, T0 + 4)]
    order = []

    class Spy(FakeAdapter):
        def transfers(self, addr):
            order.append(addr)
            return super().transfers(addr)

    trace("S", Spy(ts), labels={})
    assert order.index("BIG") < order.index("SMALL")


def test_cycle_terminates_without_duplicates():
    ts = [tx("V", "S", 1000, T0), tx("S", "A", 1000, T0 + 1), tx("A", "B", 1000, T0 + 2), tx("B", "A", 1000, T0 + 3)]
    g = trace("S", FakeAdapter(ts), labels={})
    ids = [n.id for n in g.nodes]
    assert len(ids) == len(set(ids))


# ---- pass-through
def test_pass_through_thresholds():
    t = [tx("X", "A", 1000, T0), tx("A", "B", 950, T0 + 1800)]
    assert is_pass_through(t, "A", T0, 1000)
    assert not is_pass_through([tx("A", "B", 500, T0 + 60)], "A", T0, 1000)       # only 50% forwarded
    assert not is_pass_through([tx("A", "B", 1000, T0 + 7200)], "A", T0, 1000)    # too slow
    assert not is_pass_through([], "A", T0, 0)


def test_node_types_from_pass_through():
    ts = [tx("V", "S", 1000, T0), tx("S", "FAST", 500, T0 + 1), tx("S", "SLOW", 500, T0 + 1),
          tx("FAST", "E1", 495, T0 + 100), tx("SLOW", "E2", 495, T0 + 9000)]
    got = types(trace("S", FakeAdapter(ts), labels={}))
    assert got["FAST"] == "intermediary" and got["SLOW"] == "unknown" and got["S"] == "scam_wallet"


# ---- idle funds
def test_idle_balance_and_summary_sum():
    ts = [tx("V", "S", 1000, T0), tx("S", "A", 1000, T0 + 1), tx("A", "LEAF", 600, T0 + 2)]
    assert idle_balance(ts, "LEAF") == 600 and idle_balance(ts, "A") == 400 and idle_balance(ts, "S") == 0
    g = trace("S", FakeAdapter(ts), labels={})
    assert {n.id: n.idle_balance for n in g.nodes}["LEAF"] == 600
    assert summarize(g).idle_funds == sum(n.idle_balance for n in g.nodes)


def test_unresolvable_wallet_does_not_crash():
    ts = [tx("V", "S", 1000, T0), tx("S", "GHOST", 1000, T0 + 1)]
    g = trace("S", FakeAdapter(ts), labels={})
    assert "GHOST" in types(g)


# ---- contract shape and hero case
def test_hero_trace_reaches_exchange_and_validates():
    g = trace(HERO, TronAdapter(offline=True), case_value=12000)
    Graph(**g.model_dump())
    t = types(g)
    assert t[HERO] == "scam_wallet" and t[HERO_EXCHANGE] == "exchange"
    assert sum(1 for v in t.values() if v == "intermediary") >= 2
    assert {n.id: n.hop for n in g.nodes}[HERO] == 0
    assert all(n.hop == -1 for n in g.nodes if n.type == "victim")
    assert all(isinstance(e.amount, float) and e.timestamp < 10**11 for e in g.edges)
    assert not any(e.source == HERO_EXCHANGE for e in g.edges)  # stopped at the exchange


def test_hero_build_response_is_contract_valid():
    req = TraceRequest(complaint_id="C-001", wallet=HERO, amount=12000.0)
    r = build_response(req, TronAdapter(offline=True))
    TraceResponse(**r.model_dump())
    assert r.summary.hops == 3 and r.summary.total_traced == 11800.0
    assert r.summary.idle_funds == sum(n.idle_balance for n in r.graph.nodes)
    assert r.nearest_vasp is None and r.source == "cached"


def test_invalid_address_gives_single_node_not_a_crash():
    g = trace("TXyz", TronAdapter(offline=True), case_value=1000)
    assert [n.id for n in g.nodes] == ["TXyz"] and not g.edges
