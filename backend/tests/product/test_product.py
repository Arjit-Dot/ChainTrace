"""Product-side checks (Person B): seed cases and seed traces agree with each other and the contract."""
import json
from collections import defaultdict
from pathlib import Path

import pytest

from contract.schemas import CaseSummary, TraceResponse
from paths import FIXTURES, SEED_CASES, SEED_TRACES
from product.linking import case_groups

CASES = [CaseSummary(**c) for c in json.loads(SEED_CASES.read_text())]
TRACES = {k: TraceResponse(**v) for k, v in json.loads(SEED_TRACES.read_text()).items()}


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
    from product.recommendations import build_recommendations
    hero = TraceResponse(**json.loads((FIXTURES / "trace_hero.json").read_text()))
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


# ---------- B5: PDF evidence report ----------
def _sha(case_json: dict) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(case_json, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_report_is_a_real_pdf_with_graph_and_hash(client):
    r = client.get("/api/cases/C-001/report")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert 'filename="C-001_evidence_report.pdf"' in r.headers["content-disposition"]
    pdf = r.content
    assert pdf.startswith(b"%PDF") and b"/Subtype /Image" in pdf  # the fund-flow graph
    digest = r.headers["x-evidence-sha256"]
    assert digest == _sha(client.get("/api/cases/C-001").json())  # anyone with the case record can check it
    assert f"sha256:{digest}".encode() in pdf


def test_report_per_case_and_missing(client):
    h1 = client.get("/api/cases/C-001/report").headers["x-evidence-sha256"]
    r6 = client.get("/api/cases/C-006/report")  # no exchange: still a report
    assert r6.status_code == 200 and r6.content.startswith(b"%PDF") and r6.headers["x-evidence-sha256"] != h1
    new = client.post("/api/trace", json={"complaint_id": "X", "wallet": HERO_WALLET}).json()
    assert client.get(f"/api/cases/{new['case_id']}/report").content.startswith(b"%PDF")
    assert client.get("/api/cases/C-999/report").status_code == 404


def test_graph_image_for_every_seed_trace():
    from product.recommendations import with_recommendations
    from product.reports import build_report, graph_png
    for t in TRACES.values():
        assert graph_png(t).startswith(b"\x89PNG")
    assert build_report(with_recommendations(TRACES["C-008"])).startswith(b"%PDF")


# ---------- B6: alerts and mock integrations ----------
@pytest.fixture
def stream(client):
    """Collect everything alerts.publish() pushes (what every open SSE tab receives)."""
    from product import alerts
    q = alerts.subscribe()
    seen = []
    yield lambda: seen.extend(q.get_nowait() for _ in range(q.qsize())) or seen
    alerts.unsubscribe(q)


def test_simulate_steps_through_the_hero_script(client, stream):
    from product import alerts
    alerts._script_step.clear()
    types = [client.post("/api/alerts/simulate").json()["type"] for _ in range(5)]
    assert types == ["FUNDS_MOVED", "REACHED_VASP", "ENTERED_MIXER", "HIGH_RISK_WALLET", "NEW_COMPLAINT_LINKED"]
    assert client.post("/api/alerts/simulate").json()["type"] == "FUNDS_MOVED"  # wraps round
    pushed = stream()
    assert len(pushed) == 6 and all(a["case_id"] == "C-001" and "(simulated)" in a["message"] for a in pushed)
    assert "3,720 USDT moved out of the Ethereum-side wallet" in pushed[0]["message"]
    assert client.get("/api/alerts").json()[0]["id"] == pushed[-1]["id"]  # newest first in history


def test_simulate_is_case_aware(client):
    a6 = client.post("/api/alerts/simulate", params={"case_id": "C-006"}).json()
    assert a6["case_id"] == "C-006" and a6["type"] != "REACHED_VASP"  # C-006 never reached an exchange
    assert client.post("/api/alerts/simulate", params={"case_id": "C-999"}).status_code == 404


def test_ncrp_complaint_creates_a_linked_case_and_alerts(client, stream):
    before = len(client.get("/api/cases").json())
    ack = client.post("/api/integrations/ncrp/complaints",
                      json={"complaint_id": "NCRP-FEED-1", "wallet": HERO_WALLET, "amount": 9000}).json()
    cases = client.get("/api/cases").json()
    assert len(cases) == before + 1 and ack["case_id"] == cases[0]["case_id"] and ack["status"] == "queued"
    pushed = {a["type"]: a for a in stream()}
    assert "NET-1" in pushed["NEW_COMPLAINT_LINKED"]["message"] and "HIGH_RISK_WALLET" in pushed
    assert all(a["case_id"] == ack["case_id"] for a in pushed.values())


def test_new_complaint_form_also_alerts(client, stream):
    t = client.post("/api/trace", json={"complaint_id": "X", "wallet": HERO_WALLET}).json()
    assert any(a["type"] == "NEW_COMPLAINT_LINKED" and a["case_id"] == t["case_id"] for a in stream())


def test_sahyog_send_marks_the_notice_sent(client):
    n = client.get("/api/cases/C-001/freeze-notice").json()
    assert n["status"] == "draft"
    body = {k: n[k] for k in ("case_id", "to_vasp", "subject", "body")}
    ack = client.post("/api/integrations/sahyog/notice", json=body).json()
    assert ack["case_id"] == "C-001" and ack["status"] == "received"
    assert next(c for c in client.get("/api/cases").json() if c["case_id"] == "C-001")["status"] == "notice_sent"
    assert client.get("/api/cases/C-001/freeze-notice").json()["status"] == "sent"
    assert client.post("/api/integrations/sahyog/notice", json={**body, "case_id": "C-006"}).status_code == 409
    assert client.post("/api/integrations/sahyog/notice", json={**body, "case_id": "C-999"}).status_code == 404


def test_openapi_lists_every_route():
    import main
    paths = main.app.openapi()["paths"]
    for p in ("/api/alerts/stream", "/api/alerts/simulate", "/api/integrations/ncrp/complaints",
              "/api/integrations/sahyog/notice", "/api/cases/{case_id}/report"):
        assert p in paths


# ---------- B7: dashboard and networks from the store ----------
def test_dashboard_is_computed_from_the_store(client):
    d = client.get("/api/dashboard").json()
    assert d["total_cases"] == len(CASES)
    assert d["total_amount_lost"] == pytest.approx(sum(c.amount_lost for c in CASES))
    assert d["total_amount_traced"] == pytest.approx(sum(t.summary.total_traced for t in TRACES.values()))
    assert d["idle_funds_flagged"] == pytest.approx(sum(t.summary.idle_funds for t in TRACES.values()))
    assert d["vasp_identified_pct"] == pytest.approx(100 * sum(c.vasp is not None for c in CASES) / len(CASES), abs=0.1)
    assert sum(x["count"] for x in d["by_fraud_type"]) == len(CASES)
    assert d["top_vasps"][0] == {"name": "Example Exchange A", "count": 3, "amount": 26300.0}


def test_dashboard_changes_after_an_ncrp_complaint(client):
    before = client.get("/api/dashboard").json()
    client.post("/api/integrations/ncrp/complaints",
                json={"complaint_id": "NCRP-FEED-2", "wallet": HERO_WALLET, "amount": 5000, "state": "Kerala"})
    after = client.get("/api/dashboard").json()
    assert after["total_cases"] == before["total_cases"] + 1
    assert after["total_amount_lost"] == before["total_amount_lost"] + 5000
    assert {"name": "Kerala", "count": 1, "amount": 5000.0} in after["by_state"]
    assert after["top_vasps"][0]["count"] == 4


def test_networks_come_from_shared_wallets(client):
    nets = {n["network_id"]: n for n in client.get("/api/networks").json()}
    assert set(nets) == {"NET-1", "NET-2"}
    n1 = nets["NET-1"]
    assert n1["complaint_ids"] == ["C-001", "C-002", "C-003"] and n1["vasp"] == "Example Exchange A"
    assert n1["total_amount"] == 26300.0 and n1["victim_count"] == 3
    ids = {x["id"] for x in n1["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in n1["edges"])
    deposit = TRACES["C-001"].nearest_vasp.deposit_address
    assert {"source": "C-002", "target": deposit} in n1["edges"]
    assert {x["type"] for x in n1["nodes"]} == {"complaint", "wallet", "exchange"}


def test_ncrp_case_on_a_known_wallet_joins_the_network(client):
    ack = client.post("/api/integrations/ncrp/complaints", json={"complaint_id": "NCRP-FEED-3", "wallet": HERO_WALLET}).json()
    n1 = next(n for n in client.get("/api/networks").json() if n["network_id"] == "NET-1")
    assert ack["case_id"] in n1["complaint_ids"] and n1["victim_count"] == 4
