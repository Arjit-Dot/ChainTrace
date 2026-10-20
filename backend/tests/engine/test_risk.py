"""Step 6.6: risk, reasons and typology on the traced graph, and through the engine seam."""
import json
import time

import pytest

import engine
from contract.schemas import Edge, Graph, Node, TraceRequest, TraceResponse
from engine.chains.tron import TronAdapter
from engine.model.risk import LABELED, score_graph
from engine.model.scoring import TRUNCATED_REASON
from paths import SCENARIOS_JSON
from tests.support import FakeAdapter, T0, tx

HERO = "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo"
SCENARIOS = {s["key"]: s for s in json.loads(SCENARIOS_JSON.read_text())}


def run(wallet, amount):
    return engine.trace_complaint(TraceRequest(complaint_id="R", wallet=wallet, amount=amount))


@pytest.fixture(scope="module")
def hero():
    return run(HERO, 12000.0)


def by_type(t, kind):
    return [n for n in t.graph.nodes if n.type == kind]


# ---- the hero case end to end
def test_reported_wallet_is_not_scored_but_carries_the_typology(hero):
    reported = next(n for n in hero.graph.nodes if n.hop == 0)
    assert reported.risk is None and reported.risk_score is None
    assert reported.typology == "investment_scam" and reported.reasons and "payers" in reported.reasons[0]
    assert hero.risk is None and hero.risk_score is None and hero.typology == "investment_scam"


def test_victims_are_left_alone(hero):
    for v in by_type(hero, "victim"):
        assert (v.risk, v.risk_score, v.reasons, v.typology) == ("Low", 0.0, [], "unknown")


def test_pass_through_wallets_are_high_or_critical_with_readable_reasons(hero):
    mules = [n for n in hero.graph.nodes if n.type == "intermediary" and n.hop == 1]
    assert len(mules) == 2
    for m in mules:
        assert m.risk in ("High", "Critical") and 0.5 <= m.risk_score <= 1.0
        assert 2 <= len(m.reasons) <= 3 and all(isinstance(r, str) and r for r in m.reasons)
        assert m.typology == "investment_scam"                       # risky wallets carry the case typology


def test_exchange_wallets_are_low_with_the_labeled_reasons(hero):
    deposit = next(n for n in by_type(hero, "exchange") if (n.label or "").endswith("(deposit address)"))
    hot = next(n for n in by_type(hero, "exchange") if n.id != deposit.id)
    assert (deposit.risk, deposit.risk_score, deposit.reasons) == ("Low", 0.12, ["Behaves like an exchange deposit address"])
    assert (hot.risk, hot.risk_score, hot.reasons) == ("Low", 0.05, ["Labeled exchange hot wallet"])
    assert deposit.typology == hot.typology == "unknown"             # low risk wallets do not carry a scam type


def test_bridge_is_medium_and_the_response_is_contract_valid(hero):
    assert [(n.risk, n.risk_score) for n in by_type(hero, "bridge")] == [("Medium", 0.45)]
    TraceResponse(**hero.model_dump())


# ---- the scenarios
def test_mixer_scenario_ends_at_a_critical_mixer():
    s = SCENARIOS["mixer"]
    t = run(s["wallet"], s["amount"])
    (mixer,) = by_type(t, "mixer")
    assert (mixer.risk, mixer.risk_score, mixer.reasons) == ("Critical", 0.91, ["Known mixing service"])


def test_every_scenario_scores_every_downstream_wallet_validly():
    for key, s in SCENARIOS.items():
        t = run(s["wallet"], s["amount"])
        for n in t.graph.nodes:
            if n.hop >= 1:
                assert n.risk in ("Low", "Medium", "High", "Critical") and 0 <= n.risk_score <= 1 and n.reasons, (key, n.id)
            if n.hop == 0:
                assert n.risk is None
        TraceResponse(**t.model_dump())


def test_a_wallet_that_is_not_cached_gets_a_valid_answer_not_a_crash():
    t = run("TXyz", 1000.0)                      # not even a TRON address
    assert [n.id for n in t.graph.nodes] == ["TXyz"] and t.typology == "unknown" and t.graph.nodes[0].risk is None


# ---- score_graph on its own
def graph_of(*nodes, edges=()):
    return Graph(nodes=list(nodes), edges=list(edges))


def edge(a, b, amount=1000.0, ts=T0 + 10):
    return Edge(source=a, target=b, tx_hash=f"{a}{b}", amount=amount, timestamp=ts)


def test_the_input_graph_is_not_modified():
    ts = [tx("V", "S", 1000, T0), tx("S", "M", 1000, T0 + 10), tx("M", "X", 990, T0 + 400)]
    g = graph_of(Node(id="V", type="victim", hop=-1), Node(id="S", type="scam_wallet", hop=0), Node(id="M", type="intermediary", hop=1),
                 edges=[edge("V", "S", ts=T0), edge("S", "M")])
    before = g.model_dump()
    new, _ = score_graph(g, FakeAdapter(ts), "S")
    assert g.model_dump() == before and new.nodes[2].risk is not None


def test_other_chains_are_not_scored():
    g = graph_of(Node(id="S", type="scam_wallet", hop=0), Node(id="0xabc", type="intermediary", hop=1, chain="ethereum"))
    new, _ = score_graph(g, FakeAdapter([tx("V", "S", 1000, T0)]), "S")
    eth = new.nodes[1]
    assert (eth.risk, eth.risk_score, eth.reasons) == ("Low", 0.0, [])      # untouched default


def test_a_truncated_wallet_is_capped_and_says_so():
    class Partly(FakeAdapter):
        def history_truncated(self, addr):
            return addr == "M"
    ts = [tx("V", "S", 1000, T0), tx("S", "M", 1000, T0 + 10), tx("M", "X", 995, T0 + 300)]
    g = graph_of(Node(id="S", type="scam_wallet", hop=0), Node(id="M", type="intermediary", hop=1), edges=[edge("V", "S", ts=T0), edge("S", "M")])
    plain, _ = score_graph(g, FakeAdapter(ts), "S")
    capped, _ = score_graph(g, Partly(ts), "S")
    assert plain.nodes[1].risk in ("High", "Critical")
    assert capped.nodes[1].risk in ("Low", "Medium") and capped.nodes[1].reasons[0] == TRUNCATED_REASON


def test_arrival_time_is_when_funds_first_reached_the_wallet():
    old = "OLD"
    ts = [tx(old, "M", 5, T0 - 40 * 86400), tx("S", "M", 1000, T0 + 10), tx("M", "X", 990, T0 + 400)]
    g = graph_of(Node(id="S", type="scam_wallet", hop=0), Node(id="M", type="intermediary", hop=1), edges=[edge("S", "M", ts=T0 + 10)])
    new, _ = score_graph(g, FakeAdapter(ts), "S")
    assert not any("under a day old" in r for r in new.nodes[1].reasons)      # it is 40 days old at arrival


def test_labeled_values_match_the_hero_fixture():
    fixture = json.loads((TronAdapter(offline=True).cache_dir.parents[1] / "fixtures" / "trace_hero.json").read_text())
    nodes = {n["type"]: n for n in fixture["graph"]["nodes"]}
    assert (nodes["bridge"]["risk"], nodes["bridge"]["risk_score"]) == LABELED["bridge"][:2]
    assert (nodes["mixer"]["risk"], nodes["mixer"]["risk_score"]) == LABELED["mixer"][:2]


def test_scoring_a_trace_is_fast():
    start = time.time()
    run(HERO, 12000.0)
    assert time.time() - start < 5
