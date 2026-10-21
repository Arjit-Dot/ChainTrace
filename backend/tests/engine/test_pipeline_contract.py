"""A7.3: every wallet in the cache, traced end to end, must satisfy the contract and finish in time."""
import time

import pytest

import engine
from contract.schemas import TraceRequest
from paths import SCENARIOS_JSON, TRON_CACHE
from tests.support import FakeAdapter, T0, assert_trace_invariants, tx

import base58
import hashlib
import json

TIME_LIMIT = 5.0                                    # seconds for one cached trace, the plan's acceptance bar
CACHED = sorted(p.stem for p in TRON_CACHE.glob("*.json"))
HERO = "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo"
SCENARIOS = {s["key"]: s for s in json.loads(SCENARIOS_JSON.read_text())}


def timed_trace(wallet, amount=None):
    start = time.perf_counter()
    t = engine.trace_complaint(TraceRequest(complaint_id="P", wallet=wallet, amount=amount))
    return t, time.perf_counter() - start


def test_the_cache_is_big_enough_to_mean_something():
    assert len(CACHED) >= 30


@pytest.mark.parametrize("wallet", CACHED)
def test_every_cached_wallet_traces_to_a_valid_contract_response_in_time(wallet):
    t, seconds = timed_trace(wallet)
    assert_trace_invariants(t)
    assert seconds < TIME_LIMIT, f"{wallet} took {seconds:.2f}s"


@pytest.mark.parametrize("key", sorted(SCENARIOS))
def test_every_scenario_traces_to_a_valid_contract_response_in_time(key):
    s = SCENARIOS[key]
    t, seconds = timed_trace(s["wallet"], s["amount"])
    assert_trace_invariants(t)
    assert seconds < TIME_LIMIT


def test_the_hero_trace_is_valid_fast_and_matches_its_expected_shape():
    t, seconds = timed_trace(HERO, 12000.0)
    assert_trace_invariants(t)
    assert seconds < TIME_LIMIT and t.nearest_vasp.vasp == "Example Exchange A" and t.typology == "investment_scam"
    assert (t.summary.hops, t.summary.nodes, t.summary.total_traced) == (3, 9, 11800.0) and t.notes is None


def test_the_real_second_hop_wallets_all_pass_too():
    """The wallets with the most transfers (and so the most nodes to score) are the slowest: check them alone."""
    slow = [w for w in CACHED if len(json.loads((TRON_CACHE / f"{w}.json").read_text())["data"]) >= 150]
    assert slow
    for w in slow:
        t, seconds = timed_trace(w, 100000.0)
        assert_trace_invariants(t)
        assert seconds < TIME_LIMIT


def test_a_stress_trace_stays_inside_the_time_limit_and_the_wallet_budget(monkeypatch):
    root = base58.b58encode_check(b"\x41" + hashlib.sha256(b"stress").digest()[:20]).decode()
    ts = [tx("V", root, 1_000_000, T0)]
    for i in range(150):
        ts.append(tx(root, f"A{i}", 20_000.0 + i, T0 + 10 + i))
        for j in range(5):
            ts.append(tx(f"A{i}", f"B{i}_{j}", 12_000.0 + j, T0 + 500 + i + j))
    monkeypatch.setattr(engine, "_adapter", lambda: FakeAdapter(ts))
    start = time.perf_counter()
    t = engine.trace_complaint(TraceRequest(complaint_id="X", wallet=root, amount=1_000_000.0))
    assert time.perf_counter() - start < TIME_LIMIT
    assert "wallet limit" in t.notes and t.summary.nodes <= 1 + 1 + 150 + 40 * 5


def test_total_time_for_the_whole_cache_is_small():
    start = time.perf_counter()
    for w in CACHED:
        timed_trace(w)
    assert time.perf_counter() - start < 30


# ---- through the API
@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ENGINE_MODE", "engine")
    with TestClient(main.app) as c:
        yield c


@pytest.mark.parametrize("wallet,amount", [(HERO, 12000.0), ("TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z", 100000.0), (SCENARIOS["sweep"]["wallet"], 5000.0)])
def test_the_api_returns_the_same_valid_trace_within_the_limit(client, wallet, amount):
    start = time.perf_counter()
    r = client.post("/api/trace", json={"complaint_id": "API", "wallet": wallet, "amount": amount})
    assert r.status_code == 200 and time.perf_counter() - start < TIME_LIMIT
    body = r.json()
    assert body["wallet"] == wallet and body["source"] != "simulated" and body["graph"]["nodes"]
    assert body["urgency"] in ("act_now", "act_soon", "preserve") and body["monitoring"]["status"] == "live"
