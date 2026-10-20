"""Attribution engine (Step 5): contacts, sweep stats, confidence, direct vs heuristic, none, hero."""
import time

import pytest

import engine
from contract.schemas import Graph, TraceRequest
from engine.chains.tron import TronAdapter
from engine.trace.attribution import HEURISTIC_CAP, attribute, confidence, load_contacts, sweep_stats, vasp_name
from engine.trace.tracing import load_labels, trace
from tests.support import FakeAdapter, tx

HERO = "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo"
T0 = 1_700_000_000
LABELS = {"HOT": ("Example Exchange A (hot wallet)", "exchange")}


def deposit_world(senders=14, forward=1.0):
    """Victim -> scam S -> D (deposit address, many senders) -> labeled HOT."""
    ts = [tx("V", "S", 1000, T0), tx("S", "D", 1000, T0 + 10)]
    ts += [tx(f"U{i}", "D", 100, T0 + 20 + i) for i in range(senders - 1)]
    total = 1000 + 100 * (senders - 1)
    ts.append(tx("D", "HOT", total * forward, T0 + 500))
    return ts


# ---- contacts
def test_contacts_and_name_matching():
    contacts = load_contacts()
    assert vasp_name("Example Exchange A (hot wallet)") == "Example Exchange A"
    assert contacts[vasp_name("Example Exchange A (hot wallet)")].endswith("example-exchange-a.test")
    assert contacts.get(vasp_name("Nobody Exchange")) is None


# ---- sweep stats
def test_sweep_stats_thresholds():
    assert sweep_stats(deposit_world(14), "D", "HOT", {"S", "V"})["senders"] == 14
    assert sweep_stats(deposit_world(2), "D", "HOT", set()) is None            # too few senders
    assert sweep_stats(deposit_world(14, forward=0.5), "D", "HOT", set()) is None  # not swept


def test_unrelated_senders_exclude_traced_wallets():
    stats = sweep_stats(deposit_world(14), "D", "HOT", {"S", "U0", "U1"})
    assert stats["senders"] == 14 and stats["unrelated"] == 11


# ---- confidence
def test_confidence_monotonic_and_capped():
    assert confidence(1, 0.5, 0.5) < confidence(1, 1, 0.5) < confidence(1, 1, 1) or confidence(1, 1, 1) == HEURISTIC_CAP
    assert confidence(1, 1, 1) <= HEURISTIC_CAP < 0.90
    assert confidence(0, 0, 0) == 0


# ---- attribution
def test_heuristic_attribution_on_synthetic_deposit_address():
    adapter = FakeAdapter(deposit_world())
    g = trace("S", adapter, labels=LABELS)
    vasp, g = attribute(g, adapter, LABELS, {"Example Exchange A": "x@a.test"})
    assert vasp.method == "heuristic" and vasp.deposit_address == "D" and vasp.confidence < 0.90
    assert vasp.contact == "x@a.test" and vasp.hops == 1 and vasp.amount == 1000.0
    assert {n.id: n.type for n in g.nodes}["D"] == "exchange"
    assert "D" in {n.id for n in g.nodes} and vasp.evidence


def test_direct_match_is_deterministic():
    ts = [tx("V", "S", 1000, T0), tx("S", "HOT", 1000, T0 + 10)]
    adapter = FakeAdapter(ts)
    vasp, g = attribute(trace("S", adapter, labels=LABELS), adapter, LABELS, {})
    assert vasp.method == "deterministic" and vasp.deposit_address == "HOT" and vasp.confidence >= 0.90
    assert vasp.contact is None and vasp.evidence


def test_few_senders_falls_back_to_direct_match_on_hot_wallet():
    adapter = FakeAdapter(deposit_world(senders=2))
    vasp, _ = attribute(trace("S", adapter, labels=LABELS), adapter, LABELS, {})
    assert vasp.method == "deterministic" and vasp.deposit_address == "HOT"


def test_no_exchange_returns_none():
    adapter = FakeAdapter([tx("V", "S", 1000, T0), tx("S", "A", 1000, T0 + 1)])
    g = trace("S", adapter, labels=LABELS)
    vasp, g2 = attribute(g, adapter, LABELS, {})
    assert vasp is None and g2 is g


# ---- hero and engine seam
def test_hero_attribution_matches_fixture():
    r = engine.trace_complaint(TraceRequest(complaint_id="C-001", wallet=HERO, amount=12000.0))
    v = r.nearest_vasp
    assert v.vasp == "Example Exchange A" and v.deposit_address == "TAD47AKhQdrF4P8xpbVBx3GAr6Q56BFZJ3"
    assert v.hops == 2 and v.amount == 7850.0 and v.timestamp == 1792400420
    assert v.method == "heuristic" and 0.80 <= v.confidence <= 0.89
    assert v.contact == "compliance@example-exchange-a.test" and len(v.evidence) >= 3
    ids = {n.id for n in r.graph.nodes}
    assert v.deposit_address in ids
    assert r.summary.time_to_attribution_sec is not None
    Graph(**r.graph.model_dump())


def test_uncached_wallet_has_no_vasp_and_a_note():
    r = engine.trace_complaint(TraceRequest(complaint_id="C-X", wallet="TXyz", amount=1000.0))
    assert r.nearest_vasp is None and r.notes


def test_cached_hero_trace_is_fast():
    start = time.time()
    engine.trace_complaint(TraceRequest(complaint_id="C-001", wallet=HERO, amount=12000.0))
    assert time.time() - start < 5
