"""A7.2: unusual wallets through the whole pipeline (trace, attribution, scoring, notes): valid answer, sensible note."""
import hashlib

import base58
import pytest

import engine
from contract.schemas import TraceRequest, TraceResponse
from engine.chains.tron import TronAdapter, USDT_TRC20
from tests.support import FakeAdapter, T0, tx


def tron(seed: str) -> str:
    return base58.b58encode_check(b"\x41" + hashlib.sha256(seed.encode()).digest()[:20]).decode()


S, V, A, B = tron("S"), tron("V"), tron("A"), tron("B")
HOT = "TJ4imTmNr3FZoqR2jsRBuXS2aNXNAsAXhK"                       # Example Exchange A hot wallet
HOT_B = "TRtcU89W2N6MTT7DXvpzZUAvWQ8qPTAQhS"                    # Example Exchange B hot wallet
MIXER = "TLhZTYvV5asB99Wz26sSandSaN1kZfFWbs"
BRIDGE = "TXzK7i61kT3ck6kZ3VeGZjUnPVwDS46sKM"


def run(monkeypatch, transfers, wallet=S, amount=1000.0, **req):
    monkeypatch.setattr(engine, "_adapter", lambda: FakeAdapter(transfers))
    t = engine.trace_complaint(TraceRequest(complaint_id="E", wallet=wallet, amount=amount, **req))
    TraceResponse(**t.model_dump())                          # every answer is contract-valid
    assert all(n.risk is None for n in t.graph.nodes if n.hop == 0)                # the reported wallet is never scored
    assert t.summary.nodes == len(t.graph.nodes)
    assert abs(t.summary.idle_funds - sum(n.idle_balance for n in t.graph.nodes)) < 1e-6
    return t


def by_id(t):
    return {n.id: n for n in t.graph.nodes}


# ---- cycles
def test_cycle_between_two_wallets_terminates_with_no_duplicates(monkeypatch):
    t = run(monkeypatch, [tx(V, S, 1000, T0), tx(S, A, 1000, T0 + 10), tx(A, B, 990, T0 + 20), tx(B, A, 980, T0 + 30)])
    ids = [n.id for n in t.graph.nodes]
    assert len(ids) == len(set(ids)) == 4 and t.summary.total_traced == 1000.0


def test_money_returning_to_the_reported_wallet_is_a_cycle_not_a_crash(monkeypatch):
    t = run(monkeypatch, [tx(V, S, 1000, T0), tx(S, A, 1000, T0 + 10), tx(A, S, 990, T0 + 20)])
    assert len(t.graph.nodes) == 3 and t.summary.total_traced == 1000.0


def test_paying_a_victim_back_adds_an_edge_to_the_victim_node(monkeypatch):
    t = run(monkeypatch, [tx(V, S, 1000, T0), tx(S, V, 300, T0 + 10), tx(S, A, 600, T0 + 20)])
    assert by_id(t)[V].hop == -1 and any(e.target == V for e in t.graph.edges) and by_id(t)[A].idle_balance == 600.0


# ---- empty and one-sided wallets
def test_wallet_with_no_transfers_is_one_node_with_a_clear_note(monkeypatch):
    t = run(monkeypatch, [])
    assert len(t.graph.nodes) == 1 and "No USDT transfers worth following" in t.notes and t.summary.idle_funds == 0


def test_reported_wallet_still_holding_the_money_is_idle_funds(monkeypatch):
    t = run(monkeypatch, [tx(V, S, 1000, T0)])
    root = by_id(t)[S]
    assert root.idle_balance == 1000.0 and t.summary.idle_funds == 1000.0          # the most urgent case there is


def test_wallet_that_only_sends_has_no_victims_and_the_money_is_idle_downstream(monkeypatch):
    t = run(monkeypatch, [tx(S, A, 1000, T0)], amount=None)
    assert not [n for n in t.graph.nodes if n.type == "victim"] and by_id(t)[A].idle_balance == 1000.0


def test_transfers_to_oneself_move_nothing(monkeypatch):
    t = run(monkeypatch, [tx(V, S, 1000, T0), tx(S, S, 500, T0 + 5), tx(S, A, 900, T0 + 10)])
    assert t.summary.total_traced == 900.0 and not any(e.source == e.target for e in t.graph.edges)


def test_zero_value_transfers_give_an_empty_trace_not_a_crash(monkeypatch):
    t = run(monkeypatch, [tx(V, S, 0, T0), tx(S, A, 0, T0 + 10)])
    assert len(t.graph.nodes) == 1 and t.notes


# ---- the amount in the complaint
@pytest.mark.parametrize("amount", [0.0, -5.0, None])
def test_a_missing_zero_or_negative_amount_is_not_used_and_the_trace_still_works(monkeypatch, amount):
    t = run(monkeypatch, [tx(V, S, 1000, T0), tx(S, A, 990, T0 + 10)], amount=amount)
    assert t.amount_lost is None and by_id(t)[A].idle_balance == 990.0


def test_huge_amounts_do_not_overflow(monkeypatch):
    t = run(monkeypatch, [tx(V, S, 1e15, T0), tx(S, A, 9.9e14, T0 + 10)], amount=1e15)
    assert t.summary.total_traced == pytest.approx(9.9e14)


def test_same_timestamps_do_not_confuse_the_order(monkeypatch):
    t = run(monkeypatch, [tx(V, S, 1000, T0), tx(S, A, 500, T0), tx(S, B, 500, T0)])
    assert {A, B} <= set(by_id(t))


# ---- only what happened after the victim paid
def test_transfers_before_the_victim_paid_are_not_followed(monkeypatch):
    t = run(monkeypatch, [tx(S, A, 500, T0), tx(V, S, 1000, T0 + 100)])
    assert A not in by_id(t) and by_id(t)[S].idle_balance == 500.0                  # net of what it already sent


def test_the_complaints_payment_tx_marks_the_start(monkeypatch):
    ts = [tx(V, S, 1000, T0, h="first"), tx(S, A, 400, T0 + 50), tx(V, S, 1000, T0 + 100, h="second"), tx(S, B, 700, T0 + 150)]
    both = run(monkeypatch, ts)
    only_second = run(monkeypatch, ts, tx_hash="second")
    assert {A, B} <= set(by_id(both)) and B in by_id(only_second) and A not in by_id(only_second)


# ---- the reported wallet is itself a known service
def test_reported_wallet_that_is_an_exchange_address_attributes_to_it_at_hop_zero(monkeypatch):
    t = run(monkeypatch, [tx(V, HOT, 1000, T0)], wallet=HOT)
    assert t.nearest_vasp.vasp == "Example Exchange A" and t.nearest_vasp.hops == 0 and t.nearest_vasp.deposit_address == HOT
    assert "itself a known Example Exchange A address" in t.notes and t.summary.idle_funds == 0     # at the exchange: not "idle"


def test_reported_wallet_that_is_a_mixer_or_bridge_says_so(monkeypatch):
    assert "mixing service" in run(monkeypatch, [tx(V, MIXER, 1000, T0)], wallet=MIXER).notes
    assert "cross-chain bridge" in run(monkeypatch, [tx(V, BRIDGE, 1000, T0)], wallet=BRIDGE).notes


# ---- two exchanges
def test_the_nearer_exchange_wins_and_a_tie_goes_to_the_bigger_flow(monkeypatch):
    t = run(monkeypatch, [tx(V, S, 1000, T0), tx(S, HOT, 300, T0 + 10), tx(S, HOT_B, 700, T0 + 20)])
    assert t.nearest_vasp.vasp == "Example Exchange B"                              # same hop, bigger amount
    again = run(monkeypatch, [tx(V, S, 1000, T0), tx(S, HOT, 700, T0 + 10), tx(S, HOT_B, 300, T0 + 20)])
    assert again.nearest_vasp.vasp == "Example Exchange A"


# ---- duplicates in the raw data (the real adapter)
def raw(src, dst, amount, ts, h):
    return {"transaction_id": h, "block_timestamp": ts * 1000, "from": src, "to": dst, "type": "Transfer",
            "value": str(int(amount * 10 ** 6)), "token_info": {"symbol": "USDT", "address": USDT_TRC20, "decimals": 6}}


def test_the_same_transfer_listed_twice_counts_once(tmp_path, monkeypatch):
    a = TronAdapter(cache_dir=tmp_path, offline=True)
    a.write_cache(S, [raw(V, S, 1000, T0, "d1"), raw(V, S, 1000, T0, "d1"), raw(S, A, 1000, T0 + 10, "e1"), raw(S, A, 1000, T0 + 10, "e1")])
    a.write_cache(A, [raw(S, A, 1000, T0 + 10, "e1"), raw(S, A, 1000, T0 + 10, "e1")])
    monkeypatch.setattr(engine, "_adapter", lambda: engine._Adapter(cache_dir=tmp_path, offline=True))
    t = engine.trace_complaint(TraceRequest(complaint_id="D", wallet=S, amount=1000.0))
    assert len(a.transfers(S)[0]) == 2 and t.summary.total_traced == 1000.0 and by_id(t)[A].idle_balance == 1000.0


def test_two_different_transfers_in_one_transaction_are_both_kept(tmp_path):
    a = TronAdapter(cache_dir=tmp_path, offline=True)
    a.write_cache(S, [raw(V, S, 500, T0, "same-tx"), raw(V, S, 700, T0, "same-tx")])
    assert [t.amount for t in a.transfers(S)[0]] == [500.0, 700.0]


# ---- determinism over the real cache
def test_tracing_the_same_wallet_twice_gives_the_same_answer():
    req = TraceRequest(complaint_id="R", wallet="TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu", amount=100000.0)
    a, b = engine.trace_complaint(req), engine.trace_complaint(req)
    assert a.graph == b.graph and a.nearest_vasp == b.nearest_vasp and a.typology == b.typology


def test_the_real_cached_wallets_trace_as_before():
    sizes = {}
    for name, w in [("real1", "TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z"), ("real2", "TP6jUy5qZedW2KZpJfFEEAbGVyD9kQXn6k"),
                    ("real3", "TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu")]:
        t = engine.trace_complaint(TraceRequest(complaint_id=name, wallet=w, amount=100000.0))
        sizes[name] = (len(t.graph.nodes), len(t.graph.edges))
    assert sizes == {"real1": (60, 105), "real2": (6, 22), "real3": (14, 37)}
