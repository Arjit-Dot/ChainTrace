"""A7.5: following money across a bridge onto a (seeded, SIMULATED) Ethereum side."""
import json

import pytest

import engine
from contract.schemas import TraceRequest
from engine.chains.evm_stub import EvmStubAdapter
from engine.model.risk import BRIDGED
from engine.trace.tracing import load_bridge_legs, trace
from paths import BRIDGE_LEGS, EVM_CACHE
from tests.support import FakeAdapter, T0, assert_trace_invariants, tx

HERO = "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo"
ETH_WALLET = "0x0ddd7fbade53d7c56d375dc35123c2cc4906290b"
BRIDGE = "TXzK7i61kT3ck6kZ3VeGZjUnPVwDS46sKM"             # Example Bridge (TRON to Ethereum), labeled in labels.csv


@pytest.fixture(scope="module")
def hero():
    return engine.trace_complaint(TraceRequest(complaint_id="X", wallet=HERO, amount=12000.0))


# ---- the stub adapter
def test_evm_stub_reads_seeded_transfers_and_lowercases_addresses():
    items, source = EvmStubAdapter().transfers(ETH_WALLET.upper().replace("0X", "0x"))
    assert source == "cached" and len(items) == 1 and items[0].amount == 3720.0 and items[0].to_addr == ETH_WALLET


def test_evm_stub_says_so_when_nothing_is_seeded(tmp_path):
    a = EvmStubAdapter(cache_dir=tmp_path)
    with pytest.raises(LookupError):
        a.transfers("0xabc")
    assert a.unavailable == {"0xabc": "not seeded"}


def test_the_seeded_files_are_marked_simulated():
    for p in EVM_CACHE.glob("*.json"):
        doc = json.loads(p.read_text())
        assert doc["origin"] == "scripted-evm" and "SIMULATED" in doc["note"]


def test_bridge_legs_are_keyed_by_the_tron_side_transfer():
    legs = load_bridge_legs()
    (tx_in, leg), = legs.items()
    assert leg["bridge"] == BRIDGE and leg["dest_chain"] == "ethereum" and leg["to"] == ETH_WALLET and BRIDGE_LEGS.exists()


# ---- the hero trace crosses the bridge
def test_the_hero_trace_continues_onto_ethereum_and_finds_the_idle_funds(hero):
    assert_trace_invariants(hero)
    eth = next(n for n in hero.graph.nodes if n.chain == "ethereum")
    assert eth.id == ETH_WALLET and eth.hop == 3 and eth.idle_balance == 3720.0
    assert eth.label == "Ethereum-side wallet (bridged funds)"
    assert (hero.summary.hops, hero.summary.nodes, hero.summary.idle_funds, hero.summary.total_traced) == (3, 10, 3720.0, 11800.0)


def test_the_bridge_exit_edge_is_a_bridge_edge_from_the_bridge_to_the_ethereum_wallet(hero):
    (exit_edge,) = [e for e in hero.graph.edges if e.source == BRIDGE]
    assert (exit_edge.target, exit_edge.amount, exit_edge.edge_type, exit_edge.token) == (ETH_WALLET, 3720.0, "bridge", "USDT")
    assert exit_edge.amount < next(e.amount for e in hero.graph.edges if e.target == BRIDGE)       # the bridge kept a fee


def test_the_ethereum_wallet_gets_the_fixed_bridged_funds_score_not_a_model_score(hero):
    eth = next(n for n in hero.graph.nodes if n.chain == "ethereum")
    assert (eth.risk, eth.risk_score) == BRIDGED == ("High", 0.74)
    assert eth.reasons == ["Received bridged funds from the traced flow", "No outflow yet"] and eth.typology == "investment_scam"


def test_the_live_hero_now_matches_the_fixture_on_what_matters(hero):
    fixture = json.loads((EVM_CACHE.parent.parent / "fixtures" / "trace_hero.json").read_text())
    assert hero.summary.idle_funds == fixture["summary"]["idle_funds"] == 3720.0
    assert hero.summary.hops == fixture["summary"]["hops"] and hero.nearest_vasp.vasp == fixture["nearest_vasp"]["vasp"]
    fx_eth = next(n for n in fixture["graph"]["nodes"] if n["chain"] == "ethereum")
    live_eth = next(n for n in hero.graph.nodes if n.chain == "ethereum")
    assert (live_eth.id, live_eth.hop, live_eth.idle_balance, live_eth.risk, live_eth.risk_score) == (fx_eth["id"], fx_eth["hop"], fx_eth["idle_balance"], fx_eth["risk"], fx_eth["risk_score"])


def test_the_case_is_now_act_now_with_a_continue_on_ethereum_recommendation(hero):
    from product.recommendations import build_recommendations, build_urgency
    urgency, reasons = build_urgency(hero)
    assert urgency == "act_now" and "3,720 USDT idle" in reasons[0]
    actions = [r.action for r in build_recommendations(hero)]
    assert "Act on idle funds" in actions and "Continue trace on Ethereum" in actions


def test_the_product_shows_it_end_to_end(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ENGINE_MODE", "engine")
    with TestClient(main.app) as c:
        case = c.post("/api/trace", json={"complaint_id": "XC", "wallet": HERO, "amount": 12000.0}).json()
    assert case["urgency"] == "act_now" and case["summary"]["idle_funds"] == 3720.0
    assert any(n["chain"] == "ethereum" for n in case["graph"]["nodes"])


# ---- the general mechanism, on synthetic data
S, V, M, BR = "S", "V", "M", "BRIDGE_WALLET"


def labels():
    return {BR: ("Test Bridge", "bridge")}


def legs(**over):
    leg = {"bridge": BR, "dest_chain": "ethereum", "to": "0xdest", "tx_hash": "exit1", "amount": 900.0, "timestamp": T0 + 500, "token": "USDT"}
    return {"enter1": {**leg, **over}}


def tron_world():
    return FakeAdapter([tx(V, S, 1000, T0), tx(S, BR, 950, T0 + 100, h="enter1")])


def evm_world(tmp_path, transfers):
    EVM_dir = tmp_path
    for addr, items in transfers.items():
        (EVM_dir / f"{addr}.json").write_text(json.dumps({"address": addr, "chain": "ethereum", "origin": "scripted-evm", "note": "SIMULATED",
                                                          "data": items}))
    return EvmStubAdapter(cache_dir=EVM_dir)


def test_the_trace_follows_the_money_onward_on_the_other_chain(tmp_path):
    evm = evm_world(tmp_path, {
        "0xdest": [{"tx_hash": "exit1", "from": "0xbridgeout", "to": "0xdest", "amount": 900, "timestamp": T0 + 500},
                   {"tx_hash": "e2", "from": "0xdest", "to": "0xnext", "amount": 890, "timestamp": T0 + 800}],
        "0xnext": [{"tx_hash": "e2", "from": "0xdest", "to": "0xnext", "amount": 890, "timestamp": T0 + 800}]})
    g = trace(S, tron_world(), labels=labels(), bridge_legs=legs(), evm=evm)
    nodes = {n.id: n for n in g.nodes}
    assert nodes["0xdest"].hop == 2 and nodes["0xnext"].hop == 3 and nodes["0xnext"].idle_balance == 890.0
    assert nodes["0xdest"].chain == nodes["0xnext"].chain == "ethereum"        # the chain carries on past the crossing
    assert any(e.source == "0xdest" and e.target == "0xnext" for e in g.edges)


def test_a_bridge_without_a_seeded_exit_stays_a_terminal_node():
    g = trace(S, tron_world(), labels=labels(), bridge_legs={}, evm=EvmStubAdapter(cache_dir="/nowhere"))
    assert {n.id for n in g.nodes} == {S, V, BR} and not any(e.source == BR for e in g.edges)


def test_a_leg_for_a_different_transfer_is_ignored():
    g = trace(S, tron_world(), labels=labels(), bridge_legs={"someothertx": legs()["enter1"]}, evm=EvmStubAdapter(cache_dir="/nowhere"))
    assert "0xdest" not in {n.id for n in g.nodes}


def test_a_leg_on_a_different_bridge_is_ignored():
    g = trace(S, tron_world(), labels=labels(), bridge_legs=legs(bridge="SOMEOTHERBRIDGE"), evm=EvmStubAdapter(cache_dir="/nowhere"))
    assert "0xdest" not in {n.id for n in g.nodes}


def test_a_seeded_exit_with_no_history_is_a_leaf_with_no_idle_check_crash():
    g = trace(S, tron_world(), labels=labels(), bridge_legs=legs(), evm=EvmStubAdapter(cache_dir="/nowhere"))
    dest = next(n for n in g.nodes if n.id == "0xdest")
    assert dest.chain == "ethereum" and dest.hop == 2 and dest.idle_balance == 0


def test_the_depth_limit_still_applies_after_a_crossing(tmp_path):
    g = trace(S, tron_world(), labels=labels(), bridge_legs=legs(), evm=EvmStubAdapter(cache_dir="/nowhere"), max_depth=1)
    assert "0xdest" not in {n.id for n in g.nodes}               # the bridge is at the depth limit: not expanded


def test_the_other_chain_wallet_is_not_on_the_watchlist_and_polling_does_not_crash():
    from product.alerts import watchlist
    import time
    t = engine.trace_complaint(TraceRequest(complaint_id="W", wallet=HERO, amount=12000.0))
    assert ETH_WALLET in watchlist(t)                             # it is a leaf holding funds...
    assert engine.new_transfers([ETH_WALLET], int(time.time())) == []   # ...but a non-TRON address is skipped, not an error


def test_scenarios_with_a_bridge_terminal_are_unchanged():
    scenario = next(s for s in json.loads((EVM_CACHE.parent.parent / "scenarios" / "scenarios.json").read_text()) if s["key"] == "bridge")
    t = engine.trace_complaint(TraceRequest(complaint_id="B", wallet=scenario["wallet"], amount=scenario["amount"]))
    assert not any(n.chain == "ethereum" for n in t.graph.nodes)
