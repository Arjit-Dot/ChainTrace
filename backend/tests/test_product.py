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
    assert (t.complaint_id, t.wallet) == (case.complaint_id, case.wallet)
    assert t.risk is None and case.risk is None  # reported wallet is not scored
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
    node = next(n for n in TRACES["C-004"].graph.nodes if n.hop == 1)
    r = client.get(f"/api/wallets/{node.id}/risk").json()
    assert r["risk"] == node.risk and r["risk_score"] == node.risk_score


# ---------- B4: recommendations and freeze notice ----------
def test_hero_recommendations_match_the_fixture():
    from recommendations import build_recommendations
    hero = TraceResponse(**json.loads((DATA / "fixtures" / "trace_hero.json").read_text()))
    assert build_recommendations(hero) == hero.recommendations


def test_stored_cases_carry_recommendations(client):
    c6 = client.get("/api/cases/C-006").json()["recommendations"]
    assert any(r["action"].startswith("Monitor wallet") for r in c6)
    c8 = [r["action"] for r in client.get("/api/cases/C-008").json()["recommendations"]]
    assert c8[0] == "Act on idle funds" and "Continue trace on BSC" in c8
    new = client.post("/api/trace", json={"complaint_id": "X", "wallet": HERO_WALLET}).json()
    assert [r["priority"] for r in new["recommendations"]] == ["urgent", "high", "high", "normal"]


def test_freeze_notice_is_generated_from_each_case(client):
    n1 = client.get("/api/cases/C-001/freeze-notice").json()
    n4 = client.get("/api/cases/C-004/freeze-notice").json()
    for n, cid in ((n1, "C-001"), (n4, "C-004")):
        t = TRACES[cid]
        assert n["to_vasp"] == t.nearest_vasp.vasp and n["to_email"] == t.nearest_vasp.contact
        assert t.nearest_vasp.deposit_address in n["body"] and "[LEGAL SECTION]" in n["body"]
        deposit_tx = next(e.tx_hash for e in t.graph.edges if e.target == t.nearest_vasp.deposit_address)
        assert deposit_tx in n["body"] and "IST" in n["body"] and "UTC" in n["body"]
    assert n1["body"] != n4["body"] and n1["status"] == "draft"


def test_freeze_notice_status_and_missing_vasp(client):
    assert client.get("/api/cases/C-006/freeze-notice").status_code == 404
    assert client.get("/api/cases/C-999/freeze-notice").status_code == 404
    assert client.get("/api/cases/C-003/freeze-notice").json()["status"] == "sent"
    client.get("/api/cases/C-002/freeze-notice")  # drafting moves an attributed case on
    assert next(c for c in client.get("/api/cases").json() if c["case_id"] == "C-002")["status"] == "notice_drafted"
