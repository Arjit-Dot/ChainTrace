"""A7.4: a second end-to-end case on REAL wallets that really reached a labeled exchange.

  payer -> reported wallet -> deposit address -> Binance hot wallet   (cached by data/scripts/make_real_case.py)

The wallets and transfers are real TronGrid data. The Binance label is unverified (Dune), and the reported wallet is
NOT claimed to be a scam wallet: this tests that the engine reaches and attributes a real exchange through real data.
"""
import json
import time

import pytest

import engine
from contract.schemas import TraceRequest
from engine.chains.tron import TronAdapter
from paths import SCENARIOS, TRON_CACHE
from tests.support import assert_trace_invariants

CASE = json.loads((SCENARIOS / "real_case.json").read_text())
WALLET, DEPOSIT, HOT = CASE["wallet"], CASE["deposit_address"], CASE["hot_wallet"]


def trace(wallet=WALLET, amount=None):
    start = time.perf_counter()
    t = engine.trace_complaint(TraceRequest(complaint_id="REAL", wallet=wallet, amount=amount if amount else CASE["amount"]))
    return t, time.perf_counter() - start


def test_the_case_data_is_real_not_scripted():
    assert CASE["cached_wallets"] and {WALLET, DEPOSIT, HOT} <= set(CASE["cached_wallets"])
    for w in CASE["cached_wallets"]:
        doc = json.loads((TRON_CACHE / f"{w}.json").read_text())
        assert doc["origin"] == "trongrid", w                                 # fetched live, not written by a script
    assert "not claimed to be fraud" in CASE["note"]


def test_the_trace_reaches_the_labeled_exchange_through_the_deposit_address():
    t, seconds = trace()
    assert_trace_invariants(t)
    v = t.nearest_vasp
    assert v.vasp == "Binance" and v.deposit_address == DEPOSIT and v.hops == 1
    assert v.method == "heuristic" and 0.5 <= v.confidence < 0.90             # real data, sweep pattern, never above 0.89
    assert any("labeled Binance" in e for e in v.evidence) and any("different wallets" in e for e in v.evidence)
    assert t.notes is None and seconds < 5 and t.source == "cached"


def test_the_real_graph_has_the_expected_shape():
    t, _ = trace()
    nodes = {n.id: n for n in t.graph.nodes}
    assert nodes[WALLET].hop == 0 and nodes[DEPOSIT].type == "exchange" and nodes[DEPOSIT].label == "Binance (deposit address)"
    assert nodes[HOT].type == "exchange" and nodes[HOT].hop == 2 and nodes[HOT].risk == "Low"
    assert any(e.source == DEPOSIT and e.target == HOT for e in t.graph.edges)
    assert not any(e.source == HOT for e in t.graph.edges)                      # the trace stops at the exchange


def test_every_downstream_real_wallet_is_scored_with_reasons():
    t, _ = trace()
    for n in t.graph.nodes:
        if n.hop >= 1:
            assert n.risk and 0 <= n.risk_score <= 1 and n.reasons


def test_the_same_real_flow_reported_from_the_deposit_address_is_a_direct_label_match():
    t, _ = trace(DEPOSIT, 30000.0)
    assert_trace_invariants(t)
    v = t.nearest_vasp
    assert (v.vasp, v.method, v.deposit_address, v.confidence) == ("Binance", "deterministic", HOT, 0.95)


def test_the_hot_wallets_history_is_known_to_be_partial():
    a = TronAdapter(offline=True)
    assert a.history_truncated(HOT)                                              # 200 newest transfers of a very busy wallet
    assert a.read_cache(HOT)["truncated"] is True


def test_evidence_says_days_for_a_long_lived_deposit_address():
    t, _ = trace()
    assert any("days" in e for e in t.nearest_vasp.evidence) and not any("hours" in e and "11" in e for e in t.nearest_vasp.evidence)


# ---- through the product
@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ENGINE_MODE", "engine")
    with TestClient(main.app) as c:
        yield c


def test_the_real_case_flows_through_the_whole_product(client):
    r = client.post("/api/trace", json={"complaint_id": "REAL-1", "wallet": WALLET, "amount": CASE["amount"], "state": "Delhi"})
    assert r.status_code == 200
    case = r.json()
    assert case["nearest_vasp"]["vasp"] == "Binance" and case["urgency"] in ("act_now", "act_soon", "preserve")
    notice = client.get(f"/api/cases/{case['case_id']}/freeze-notice")
    assert notice.status_code == 200 and notice.json()["to_vasp"] == "Binance"
    report = client.get(f"/api/cases/{case['case_id']}/report")
    assert report.status_code == 200 and report.content[:5] == b"%PDF-"
    summary = next(c for c in client.get("/api/cases").json() if c["case_id"] == case["case_id"])
    assert summary["vasp"] == "Binance" and summary["status"] in ("attributed", "notice_drafted")
