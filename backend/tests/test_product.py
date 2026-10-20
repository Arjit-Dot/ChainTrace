"""Product-side checks (Person B): seed cases and seed traces agree with each other and the contract."""
import json
from collections import defaultdict
from pathlib import Path

import pytest

from contract.schemas import CaseSummary, TraceResponse
from linking import case_groups

DATA = Path(__file__).resolve().parents[2] / "data"
CASES = [CaseSummary(**c) for c in json.loads((DATA / "seed_cases.json").read_text())]
TRACES = {k: TraceResponse(**v) for k, v in json.loads((DATA / "seed_traces.json").read_text()).items()}


def test_every_seed_case_has_a_trace():
    assert {c.case_id for c in CASES} == set(TRACES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_trace_matches_case(case):
    t = TRACES[case.case_id]
    assert (t.complaint_id, t.wallet, t.risk) == (case.complaint_id, case.wallet, case.risk)
    assert (t.nearest_vasp.vasp if t.nearest_vasp else None) == case.vasp
    assert t.summary.time_to_attribution_sec == case.time_to_attribution_sec


@pytest.mark.parametrize("case_id", sorted(TRACES))
def test_trace_follows_contract_rules(case_id):
    t = TRACES[case_id]
    ids = {n.id for n in t.graph.nodes}
    assert all(e.source in ids and e.target in ids for e in t.graph.edges)
    assert t.summary.nodes == len(t.graph.nodes)
    assert t.summary.idle_funds == pytest.approx(sum(n.idle_balance for n in t.graph.nodes))
    assert any(n.id == t.wallet and n.hop == 0 for n in t.graph.nodes)
    if t.nearest_vasp:
        assert t.nearest_vasp.deposit_address in ids
        assert t.nearest_vasp.evidence
        assert t.nearest_vasp.method == ("deterministic" if t.nearest_vasp.confidence >= 0.9 else "heuristic")


def test_networks_from_shared_wallets_match_network_ids():
    expected = defaultdict(set)
    for c in CASES:
        expected[c.network_id or c.case_id].add(c.case_id)  # unlinked cases stand alone
    found = sorted(sorted(g) for g in case_groups(TRACES))
    assert found == sorted(sorted(g) for g in expected.values())
    assert sum(len(g) > 1 for g in found) >= 2


# ---------- B3: case store, engine client, cases API (fixture mode) ----------
HERO_WALLET = "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo"


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("ENGINE_MODE", "fixture")
    with TestClient(main.app) as c:
        yield c


def test_each_case_serves_its_own_graph(client):
    c1, c2 = client.get("/api/cases/C-001").json(), client.get("/api/cases/C-002").json()
    assert (c1["case_id"], c2["case_id"]) == ("C-001", "C-002")
    assert c2["wallet"] == TRACES["C-002"].wallet and c1["graph"] != c2["graph"]
    assert client.get("/api/cases/C-999").status_code == 404


def test_hero_complaint_becomes_a_new_case(client):
    assert len(client.get("/api/cases").json()) == len(CASES)
    req = {"complaint_id": "NCRP-TEST-1", "wallet": HERO_WALLET, "amount": 12000, "state": "Karnataka"}
    t = client.post("/api/trace", json=req).json()
    assert t["case_id"] == "C-009" and t["complaint_id"] == "NCRP-TEST-1"

    cases = client.get("/api/cases").json()
    assert len(cases) == len(CASES) + 1 and cases[0]["case_id"] == "C-009"  # newest first
    assert cases[0]["network_id"] == "NET-1" and cases[0]["vasp"] == "Example Exchange A"
    assert client.get("/api/cases/C-009").json()["graph"] == TRACES["C-001"].model_dump()["graph"]


def test_seed_wallet_returns_its_seed_trace(client):
    t = client.post("/api/trace", json={"complaint_id": "X", "wallet": TRACES["C-006"].wallet}).json()
    assert t["nearest_vasp"] is None and t["graph"] == TRACES["C-006"].model_dump()["graph"]
    assert client.get(f"/api/cases/{t['case_id']}").status_code == 200


def test_unknown_wallet_falls_back_to_hero_graph_starting_at_that_wallet(client):
    wallet = "TXYZnotInTheDemoSet111111111111111"
    t = TraceResponse(**client.post("/api/trace", json={"complaint_id": "X", "wallet": wallet}).json())
    assert t.wallet == wallet and any(n.id == wallet and n.hop == 0 for n in t.graph.nodes)
    assert HERO_WALLET not in {n.id for n in t.graph.nodes} and t.source == "simulated" and t.notes


def test_engine_failure_falls_back_to_fixture(client, monkeypatch):
    monkeypatch.setenv("ENGINE_MODE", "http")
    monkeypatch.setenv("ENGINE_URL", "http://127.0.0.1:9")  # nothing listens here
    t = client.post("/api/trace", json={"complaint_id": "X", "wallet": HERO_WALLET}).json()
    assert t["graph"] == TRACES["C-001"].model_dump()["graph"] and "unavailable" in t["notes"]


def test_wallet_risk_reads_seed_nodes(client):
    r = client.get(f"/api/wallets/{TRACES['C-004'].wallet}/risk").json()
    assert r["risk"] == TRACES["C-004"].risk
