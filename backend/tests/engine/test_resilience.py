"""A7.1: TronGrid failures, the wallet and time budgets, and the notes that tell an officer how complete a trace is."""
import httpx
import pytest

import engine
from contract.schemas import TraceRequest, TraceResponse
from engine.chains.tron import FetchError, TronAdapter, USDT_TRC20
from engine.trace.tracing import MAX_EXPANDED, TraceStats, trace
from tests.support import FakeAdapter, T0, tx

import base58
import hashlib


def tron(seed: str) -> str:
    return base58.b58encode_check(b"\x41" + hashlib.sha256(seed.encode()).digest()[:20]).decode()


S, V, A, B = tron("s"), tron("v"), tron("a"), tron("b")


def raw(src, dst, amount, ts):
    return {"transaction_id": hashlib.sha256(f"{src}{dst}{ts}".encode()).hexdigest(), "block_timestamp": ts * 1000,
            "from": src, "to": dst, "type": "Transfer", "value": str(int(amount * 10 ** 6)),
            "token_info": {"symbol": "USDT", "address": USDT_TRC20, "decimals": 6}}


def failing_client(handler):
    return httpx.Client(base_url="https://api.trongrid.io", transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("engine.chains.tron.time.sleep", lambda s: None)      # 429 retries would otherwise wait


# ---- the adapter turns live failures into FetchError with a reason
@pytest.mark.parametrize("handler,reason", [
    (lambda r: httpx.Response(429, json={}), "rate limited"),
    (lambda r: httpx.Response(500, json={}), "server error 500"),
    (lambda r: httpx.Response(503, json={}), "server error 503"),
    (lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("slow")), "timed out"),
    (lambda r: (_ for _ in ()).throw(httpx.ConnectError("down")), "network error"),
    (lambda r: httpx.Response(200, json={"success": False, "error": "bad"}), "API error"),
])
def test_live_failure_becomes_a_fetch_error_with_a_reason(tmp_path, handler, reason):
    a = TronAdapter(cache_dir=tmp_path, client=failing_client(handler))
    with pytest.raises(FetchError) as e:
        a.transfers(S)
    assert e.value.reason == reason and isinstance(e.value, LookupError) and a.unavailable[S] == reason
    assert a.read_cache(S) is None                              # nothing half-written


def test_offline_uncached_is_recorded_as_not_cached(tmp_path):
    a = TronAdapter(cache_dir=tmp_path, offline=True)
    with pytest.raises(LookupError):
        a.transfers(S)
    assert a.unavailable[S] == "not cached"


def test_a_cached_wallet_never_touches_the_network_even_when_it_is_down(tmp_path):
    a = TronAdapter(cache_dir=tmp_path, client=failing_client(lambda r: httpx.Response(500, json={})))
    a.write_cache(S, [raw(V, S, 1000, T0)])
    assert a.transfers(S)[1] == "cached" and a.unavailable == {}


def test_a_rate_limit_that_clears_on_retry_still_succeeds(tmp_path):
    calls = []

    def handler(r):
        calls.append(1)
        return httpx.Response(429, json={}) if len(calls) < 3 else httpx.Response(200, json={"success": True, "data": [raw(V, S, 5, T0)], "meta": {}})
    a = TronAdapter(cache_dir=tmp_path, client=failing_client(handler))
    items, source = a.transfers(S)
    assert source == "live" and len(items) == 1 and a.unavailable == {}


# ---- a trace carries on past a wallet that could not be fetched
def trace_with(monkeypatch, tmp_path, handler, key=True):
    a = TronAdapter(cache_dir=tmp_path, client=failing_client(handler))
    a.write_cache(S, [raw(V, S, 1000, T0), raw(S, A, 500, T0 + 60), raw(S, B, 500, T0 + 70)])
    a.write_cache(A, [raw(S, A, 500, T0 + 60), raw(A, tron("x"), 495, T0 + 400)])
    monkeypatch.setattr(engine, "_adapter", lambda: engine._Adapter(cache_dir=tmp_path, client=a.client, offline=not key))
    return engine.trace_complaint(TraceRequest(complaint_id="R", wallet=S, amount=1000.0))


def test_failed_wallet_is_a_leaf_not_a_crash_and_the_note_says_so(monkeypatch, tmp_path):
    t = trace_with(monkeypatch, tmp_path, lambda r: httpx.Response(429, json={}))
    ids = {n.id for n in t.graph.nodes}
    assert {S, A, B} <= ids and tron("x") in ids                  # A was read from cache and followed on
    assert "2 wallet(s) could not be fetched (rate limited)" in t.notes and "incomplete" in t.notes   # B and the leaf beyond A
    TraceResponse(**t.model_dump())


def test_every_failure_kind_is_named_in_the_note(monkeypatch, tmp_path):
    t = trace_with(monkeypatch, tmp_path, lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("slow")))
    assert "timed out" in t.notes


def test_the_api_shows_the_engine_result_not_the_fixture_when_tron_grid_fails(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "c.db"))
    monkeypatch.setenv("ENGINE_MODE", "engine")
    monkeypatch.setenv("TRONGRID_API_KEY", "dummy")
    cache = tmp_path / "cache"
    seed = TronAdapter(cache_dir=cache)
    seed.write_cache(S, [raw(V, S, 1000, T0), raw(S, B, 500, T0 + 70)])
    client = failing_client(lambda r: httpx.Response(429, json={}))
    monkeypatch.setattr(engine, "_adapter", lambda: engine._Adapter(cache_dir=cache, client=client, offline=False))
    with TestClient(main.app) as c:
        body = c.post("/api/trace", json={"complaint_id": "X", "wallet": S, "amount": 1000.0}).json()
    assert body["source"] != "simulated" and "could not be fetched" in body["notes"]
    assert "Engine" not in (body["notes"] or "") and S in {n["id"] for n in body["graph"]["nodes"]}


# ---- the budgets
def wide_graph(branches=100, second_hop=True):
    ts = [tx("V", "S", 1_000_000, T0)]
    for i in range(branches):
        ts.append(tx("S", f"A{i}", 20_000.0 + 100 * i, T0 + 10 + i))      # A99 is the biggest flow, A0 the smallest
        if second_hop:
            ts.append(tx(f"A{i}", f"B{i}", 19_900.0 + 100 * i, T0 + 500 + i))
    return FakeAdapter(ts)


def test_wallet_limit_stops_the_trace_and_reads_the_biggest_flows_first():
    stats = TraceStats()
    g = trace("S", wide_graph(), case_value=1_000_000, max_expanded=10, stats=stats, labels={})
    assert stats.stopped == "wallet limit" and stats.expanded == 10
    followed = {e.source for e in g.edges if e.source.startswith("A")}
    assert "A99" in followed and "A0" not in followed                       # the smallest flows are what gets cut


def test_default_limit_is_a_sensible_bound():
    stats = TraceStats()
    trace("S", wide_graph(), case_value=1_000_000, stats=stats, labels={})
    assert stats.expanded == MAX_EXPANDED and stats.stopped == "wallet limit"


def test_a_small_trace_is_never_cut_short():
    stats = TraceStats()
    trace("S", wide_graph(branches=5), case_value=1_000_000, stats=stats, labels={})
    assert stats.stopped is None and stats.unchecked_leaves == 0


def test_time_budget_stops_the_trace_and_skips_the_idle_checks():
    now = [0.0]

    class Slow(FakeAdapter):
        def transfers(self, addr):
            now[0] += 5.0                                                    # each wallet read costs 5 simulated seconds
            return super().transfers(addr)

    stats = TraceStats()
    g = trace("S", Slow(wide_graph(30).all), case_value=1_000_000, time_budget=20.0, stats=stats, labels={}, clock=lambda: now[0])
    assert stats.stopped == "time budget" and stats.expanded < 30 and stats.unchecked_leaves > 0
    assert any(n.id == "S" for n in g.nodes)                                  # still a valid graph


def test_notes_report_the_limit_and_the_unchecked_wallets():
    stats = TraceStats(expanded=40, stopped="wallet limit", unchecked_leaves=3)
    resp = TraceResponse(case_id="c", complaint_id="c", wallet="W", risk=None, risk_score=None,
                         graph={"nodes": [], "edges": []}, summary={"hops": 0, "nodes": 0, "total_traced": 0, "idle_funds": 0},
                         source="cached", generated_at=1)
    notes = engine._notes(S, TronAdapter(offline=True), stats, resp)
    assert "stopped at the wallet limit after reading 40 wallets" in notes and "Idle balances were not checked for 3" in notes


# ---- the notes for wallets we cannot trace at all
@pytest.mark.parametrize("wallet,fragment", [
    ("0xd90e2f925da726b50c4ed8d0fb90ad053324f31b", "Ethereum wallets are not traced yet"),
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "Bitcoin wallets are not traced yet"),
    ("TXyz", "Not a valid wallet address"),
    ("", "Not a valid wallet address"),
    (tron("not-in-the-cache"), "not in the demo cache and no TronGrid key is set"),
])
def test_untraceable_wallets_get_a_clear_note(wallet, fragment):
    t = engine.trace_complaint(TraceRequest(complaint_id="N", wallet=wallet or "x", amount=100.0)) if wallet else \
        engine.trace_complaint(TraceRequest(complaint_id="N", wallet="", amount=100.0))
    assert fragment in t.notes and [n.id for n in t.graph.nodes] == [wallet or ""] and t.nearest_vasp is None


def test_a_fully_cached_attributed_trace_has_no_notes():
    t = engine.trace_complaint(TraceRequest(complaint_id="H", wallet="TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo", amount=12000.0))
    assert t.notes is None


def test_no_exchange_found_is_still_noted_for_a_complete_trace():
    t = engine.trace_complaint(TraceRequest(complaint_id="I", wallet="TJgNArE5dkoiDgHUjimdizwNaTZZwLh1Lg", amount=6000.0))
    assert t.notes == "No exchange found in the traced flow."


# ---- the watcher must not mistake a failed check for "nothing moved"
def test_a_failed_poll_raises_so_the_case_goes_stale(monkeypatch, tmp_path):
    monkeypatch.setenv("TRONGRID_API_KEY", "dummy")
    a = TronAdapter(cache_dir=tmp_path, client=failing_client(lambda r: httpx.Response(429, json={})))
    monkeypatch.setattr(engine, "_adapter", lambda: engine._Adapter(cache_dir=tmp_path, client=a.client, offline=False))
    with pytest.raises(FetchError):
        engine.new_transfers([S], 0)
