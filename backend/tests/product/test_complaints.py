"""Portal stage 2: complaint intake, the officer inbox, the trace trigger, and what a citizen can (not) see."""
import json
import re
import time

import pytest
from fastapi.testclient import TestClient

from contract.schemas import CONTRACT_VERSION, Alert, Complaint, ComplaintEvent
from paths import SEED_COMPLAINTS
from product import alerts, complaints, store

HERO = "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo"
SEED = json.loads(SEED_COMPLAINTS.read_text())
PENDING = [c for c in SEED if c["stage"] == "received"]
GOOD = {"wallet": HERO, "amount": 12000, "fraud_type": "investment", "state": "Karnataka",
        "reporter_name": "Test Citizen", "reporter_mobile": "9876543210", "description": "Paid to a fake trading app."}


@pytest.fixture
def client(tmp_path, monkeypatch):
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ENGINE_MODE", "fixture")
    monkeypatch.setenv("CHAINTRACE_MONITOR", "0")
    complaints._lookups.clear()
    complaints._tracing.clear()
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def engine_client(tmp_path, monkeypatch):
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "e.db"))
    monkeypatch.setenv("ENGINE_MODE", "engine")
    monkeypatch.setenv("CHAINTRACE_MONITOR", "0")
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def stream():
    q = alerts.subscribe()
    seen = []
    yield lambda: seen.extend(q.get_nowait() for _ in range(q.qsize())) or seen
    alerts.unsubscribe(q)


def file(client, **over):
    return client.post("/api/complaints", json={**GOOD, **over})


# ---- the contract
def test_contract_is_1_2_0_and_alerts_can_be_about_a_complaint_with_no_case():
    assert CONTRACT_VERSION == "1.2.0"
    a = Alert(id="x", type="COMPLAINT_RECEIVED", severity="info", complaint_id="NCRP-2026-000001", message="m", timestamp=1)
    assert a.case_id is None and a.complaint_id == "NCRP-2026-000001"


# ---- filing
def test_filing_issues_a_random_id_and_traces_nothing(client):
    cases_before = len(client.get("/api/cases").json())
    r = file(client)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"complaint_id", "stage", "message"} and body["stage"] == "received"
    assert re.fullmatch(r"NCRP-\d{4}-\d{6}", body["complaint_id"])
    assert len(client.get("/api/cases").json()) == cases_before                       # no trace, no case
    assert client.get(f"/api/officer/complaints/{body['complaint_id']}").json()["case_id"] is None


def test_ids_are_unique_and_not_sequential(client):
    ids = [file(client).json()["complaint_id"] for _ in range(40)]
    assert len(set(ids)) == 40
    nums = sorted(int(i[-6:]) for i in ids)
    assert any(b - a != 1 for a, b in zip(nums, nums[1:]))                            # random, not counting up


def test_filing_alerts_the_officers(client, stream):
    cid = file(client, state="Kerala").json()["complaint_id"]
    (a,) = [x for x in stream() if x["type"] == "COMPLAINT_RECEIVED"]
    assert a["complaint_id"] == cid and a["case_id"] is None and "Kerala" in a["message"] and a["severity"] == "info"


@pytest.mark.parametrize("over", [
    {"wallet": ""}, {"reporter_name": ""}, {"reporter_mobile": "12345"}, {"reporter_mobile": "98765abcde"},
    {"reporter_mobile": "98765432101"}, {"amount": -5}, {"chain": "dogecoin"}, {"description": "x" * 2001}, {"wallet": "T" * 121},
])
def test_bad_complaints_are_rejected_and_not_stored(client, over):
    n = len(client.get("/api/officer/complaints").json())
    assert file(client, **over).status_code == 422
    assert len(client.get("/api/officer/complaints").json()) == n


def test_missing_required_fields_are_rejected(client):
    for field in ("wallet", "reporter_name", "reporter_mobile"):
        body = {k: v for k, v in GOOD.items() if k != field}
        assert client.post("/api/complaints", json=body).status_code == 422


def test_the_citizen_receipt_never_contains_the_complaint_details(client):
    text = file(client).text
    for secret in (HERO, "Test Citizen", "9876543210", "12000", "Karnataka"):
        assert secret not in text


# ---- what a citizen can see
PUBLIC_KEYS = {"complaint_id", "stage", "label", "message", "updated_at", "timeline"}
FORBIDDEN = [HERO, "Test Citizen", "9876543210", "12000", "Karnataka", "case_id", "wallet", "exchange", "vasp", "trace", "graph",
             "freeze", "bank", "risk", "Example", "C-0"]


def test_the_status_has_only_the_stage_and_generic_messages(client):
    cid = file(client).json()["complaint_id"]
    r = client.get(f"/api/complaints/{cid}/status")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == PUBLIC_KEYS
    assert (body["stage"], body["label"], body["message"]) == ("received", "Received", "Your complaint has been registered.")
    assert [set(t) for t in body["timeline"]] == [{"stage", "label", "message", "at"}]
    low = r.text.lower()
    for word in FORBIDDEN:
        assert word.lower() not in low, word


def test_the_status_follows_the_officers_steps_without_revealing_them(client):
    cid = file(client).json()["complaint_id"]
    stages = []
    for step in ("review", "trace"):
        client.post(f"/api/officer/complaints/{cid}/{step}")
        view = client.get(f"/api/complaints/{cid}/status")
        stages.append(view.json()["stage"])
        assert set(view.json()) == PUBLIC_KEYS
        for word in FORBIDDEN:
            assert word.lower() not in view.text.lower(), (step, word)
    assert stages == ["under_review", "investigating"]
    final = client.get(f"/api/complaints/{cid}/status").json()
    assert [t["stage"] for t in final["timeline"]] == ["received", "under_review", "investigating"]
    assert final["message"] == "Your complaint is being investigated." and final["label"] == "Investigation in progress"


def test_seeded_complaints_show_their_stage(client):
    for c in SEED:
        v = client.get(f"/api/complaints/{c['complaint_id']}/status").json()
        assert v["stage"] == c["stage"] and set(v) == PUBLIC_KEYS


def test_an_unknown_id_gets_one_generic_answer(client):
    for bad in ("NCRP-2026-000000", "nope", "' OR 1=1 --", "NCRP-2026-1; DROP TABLE complaints", "%00", "A" * 300):
        r = client.get(f"/api/complaints/{bad}/status")
        assert r.status_code == 404 and r.json()["detail"] == complaints.NOT_FOUND
    assert len(client.get("/api/officer/complaints").json()) == len(SEED)             # nothing was damaged


def test_an_id_with_spaces_around_it_still_works(client):
    cid = file(client).json()["complaint_id"]
    assert client.get(f"/api/complaints/%20{cid}%20/status").status_code == 200


def test_the_public_view_is_built_from_stage_alone_so_nothing_else_can_leak():
    rec = Complaint(complaint_id="NCRP-2026-000009", wallet="SECRETWALLET", reporter_name="SECRETNAME", reporter_mobile="9999999999",
                    amount=777.0, stage="investigating", case_id="C-999", created_at=100, updated_at=300,
                    history=[ComplaintEvent(at=100, stage="received", note="SECRETNOTE wallet"),
                             ComplaintEvent(at=200, stage="under_review", note="SECRETNOTE binance"),
                             ComplaintEvent(at=250, stage="under_review", note="again SECRETNOTE"),
                             ComplaintEvent(at=300, stage="investigating", note="SECRETNOTE case C-999")])
    text = complaints.public_view(rec).model_dump_json()
    for secret in ("SECRET", "C-999", "777", "9999999999"):
        assert secret not in text
    assert [t.stage for t in complaints.public_view(rec).timeline] == ["received", "under_review", "investigating"]  # no repeats


def test_every_stage_has_its_own_label_and_message():
    assert set(complaints.STAGES) == set(complaints.LABELS) == set(complaints.MESSAGES)
    assert len(set(complaints.MESSAGES.values())) == 5


# ---- rate limiting the status lookup
def test_too_many_lookups_are_refused_then_allowed_again(client, monkeypatch):
    monkeypatch.setattr(complaints, "STATUS_LIMIT", 5)
    for _ in range(5):
        assert client.get("/api/complaints/NCRP-2026-111111/status").status_code == 404
    r = client.get("/api/complaints/NCRP-2026-111111/status")
    assert r.status_code == 429 and "wait" in r.json()["detail"].lower()
    for window in complaints._lookups.values():                                       # a minute passes
        window.clear()
        window.extend([time.time() - 120] * 5)
    assert client.get("/api/complaints/NCRP-2026-111111/status").status_code == 404


# ---- the officer inbox
def test_the_inbox_lists_new_and_seeded_complaints_newest_first(client):
    cid = file(client).json()["complaint_id"]
    inbox = client.get("/api/officer/complaints").json()
    assert inbox[0]["complaint_id"] == cid and len(inbox) == len(SEED) + 1
    times = [c["created_at"] for c in inbox]
    assert times == sorted(times, reverse=True)


def test_the_inbox_can_be_filtered_by_stage(client):
    new = client.get("/api/officer/complaints", params={"stage": "received"}).json()
    assert {c["complaint_id"] for c in new} == {c["complaint_id"] for c in PENDING}
    assert all(c["stage"] == "investigating" for c in client.get("/api/officer/complaints", params={"stage": "investigating"}).json())
    assert client.get("/api/officer/complaints", params={"stage": "bogus"}).status_code == 422


def test_an_officer_sees_the_full_complaint(client):
    cid = file(client).json()["complaint_id"]
    c = client.get(f"/api/officer/complaints/{cid}").json()
    assert (c["wallet"], c["reporter_name"], c["reporter_mobile"], c["amount"]) == (HERO, "Test Citizen", "9876543210", 12000)
    assert c["history"][0]["stage"] == "received" and c["stage"] == "received"
    assert client.get("/api/officer/complaints/NCRP-NOPE").status_code == 404


# ---- review and the trace trigger
def test_review_moves_a_new_complaint_forward_once(client):
    cid = file(client).json()["complaint_id"]
    r = client.post(f"/api/officer/complaints/{cid}/review")
    assert r.status_code == 200 and r.json()["stage"] == "under_review" and r.json()["history"][-1]["stage"] == "under_review"
    assert client.post(f"/api/officer/complaints/{cid}/review").status_code == 409
    assert client.post("/api/officer/complaints/NCRP-NOPE/review").status_code == 404


def test_triggering_the_trace_creates_the_case_and_links_it(client):
    cid = file(client).json()["complaint_id"]
    cases_before = {c["case_id"] for c in client.get("/api/cases").json()}
    done = client.post(f"/api/officer/complaints/{cid}/trace")
    assert done.status_code == 200
    rec = done.json()
    (new_case,) = {c["case_id"] for c in client.get("/api/cases").json()} - cases_before
    assert rec["case_id"] == new_case and rec["stage"] == "investigating"
    assert "Trace triggered" in rec["history"][-1]["note"] and new_case in rec["history"][-1]["note"]
    case = client.get(f"/api/cases/{new_case}").json()
    assert case["complaint_id"] == cid and case["wallet"] == HERO


def test_the_trace_can_be_triggered_after_a_review_too(client):
    cid = file(client).json()["complaint_id"]
    client.post(f"/api/officer/complaints/{cid}/review")
    assert client.post(f"/api/officer/complaints/{cid}/trace").json()["stage"] == "investigating"


def test_a_trace_cannot_be_triggered_twice(client):
    cid = file(client).json()["complaint_id"]
    client.post(f"/api/officer/complaints/{cid}/trace")
    n = len(client.get("/api/cases").json())
    r = client.post(f"/api/officer/complaints/{cid}/trace")
    assert r.status_code == 409 and len(client.get("/api/cases").json()) == n
    assert client.post(f"/api/officer/complaints/{SEED[0]['complaint_id']}/trace").status_code == 409     # already investigating


def test_a_trace_already_running_is_refused(client):
    cid = file(client).json()["complaint_id"]
    complaints._tracing.add(cid)
    assert client.post(f"/api/officer/complaints/{cid}/trace").status_code == 409
    complaints._tracing.clear()
    assert client.post(f"/api/officer/complaints/{cid}/trace").status_code == 200


def test_a_failed_trace_does_not_leave_the_complaint_stuck(client, monkeypatch):
    cid = file(client).json()["complaint_id"]

    async def boom(req):
        raise RuntimeError("engine down")
    monkeypatch.setattr("product.integrations.create_case", boom)
    with pytest.raises(RuntimeError):
        client.post(f"/api/officer/complaints/{cid}/trace")
    assert cid not in complaints._tracing and client.get(f"/api/officer/complaints/{cid}").json()["stage"] == "received"


def test_tracing_raises_the_case_alerts_after_the_complaint_alert(client, stream):
    cid = file(client).json()["complaint_id"]
    client.post(f"/api/officer/complaints/{cid}/trace")
    types = [a["type"] for a in stream()]
    assert types[0] == "COMPLAINT_RECEIVED" and ("HIGH_RISK_WALLET" in types or "NEW_COMPLAINT_LINKED" in types)


# ---- real tracing of the seeded waiting complaints (engine mode)
def test_the_waiting_demo_complaints_trace_to_different_outcomes(engine_client):
    by_wallet = {c["wallet"]: c["complaint_id"] for c in PENDING}
    outcomes = {}
    for wallet, cid in by_wallet.items():
        rec = engine_client.post(f"/api/officer/complaints/{cid}/trace").json()
        case = engine_client.get(f"/api/cases/{rec['case_id']}").json()
        outcomes[cid] = (case["nearest_vasp"] and case["nearest_vasp"]["vasp"], case["summary"]["idle_funds"])
    assert outcomes["NCRP-2026-104317"][0] == "Example Exchange B"                      # sweep scenario: a VASP
    assert outcomes["NCRP-2026-258846"] == (None, 5900.0)                               # idle funds, no VASP yet
    assert outcomes["NCRP-2026-391502"][0] == "Binance"                                 # the real flow


# ---- the NCRP feed
def test_the_ncrp_feed_is_idempotent_by_complaint_id(client, stream):
    body = {"complaint_id": "NCRP-FEED-9", "wallet": HERO, "amount": 100}
    a1 = client.post("/api/integrations/ncrp/complaints", json=body).json()
    a2 = client.post("/api/integrations/ncrp/complaints", json=body).json()
    assert a1["ack_id"] == a2["ack_id"] == "NCRP-ACK-NCRP-FEED-9"
    assert len([c for c in client.get("/api/officer/complaints").json() if c["complaint_id"] == "NCRP-FEED-9"]) == 1
    assert len([a for a in stream() if a["type"] == "COMPLAINT_RECEIVED"]) == 1


# ---- the seed and persistence
def test_the_seed_has_one_complaint_per_case_plus_waiting_ones(client):
    assert len(SEED) == 11 and len(PENDING) == 3
    linked = {c["complaint_id"]: c["case_id"] for c in SEED if c["case_id"]}
    for case in client.get("/api/cases").json():
        if case["case_id"] in linked.values():
            assert linked[case["complaint_id"]] == case["case_id"]
    assert {c["complaint_id"] for c in SEED if c["case_id"]} == {f"NCRP-2026-{i:04d}" for i in range(1, 9)}
    assert next(c for c in SEED if c["case_id"] == "C-003")["stage"] == "action_initiated"       # notice already sent


def test_restarting_does_not_undo_an_officers_progress(client):
    cid = PENDING[0]["complaint_id"]
    client.post(f"/api/officer/complaints/{cid}/trace")
    store.init()                                                                       # what happens on every server start
    assert store.get_complaint(cid).stage == "investigating" and store.get_complaint(cid).case_id


def test_a_reset_wipes_the_complaints_and_reseeds(client):
    file(client)
    store.init(reset=True)
    assert len(store.list_complaints()) == len(SEED)


def test_complaints_survive_a_new_session(tmp_path, monkeypatch):
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("ENGINE_MODE", "fixture")
    monkeypatch.setenv("CHAINTRACE_MONITOR", "0")
    with TestClient(main.app) as c:
        cid = file(c).json()["complaint_id"]
    with TestClient(main.app) as c:
        assert c.get(f"/api/complaints/{cid}/status").status_code == 200


def test_openapi_lists_the_complaint_routes():
    import main
    paths = main.app.openapi()["paths"]
    for p in ("/api/complaints", "/api/complaints/{complaint_id}/status", "/api/officer/complaints",
              "/api/officer/complaints/{complaint_id}", "/api/officer/complaints/{complaint_id}/review",
              "/api/officer/complaints/{complaint_id}/trace"):
        assert p in paths
