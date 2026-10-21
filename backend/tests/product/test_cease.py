"""Stage 5: report and cease, the complaint stage it drives, closing, and the four seeded demo cases."""
import pytest
from fastapi.testclient import TestClient

from product import complaints

VASP, DEX, BANK, STALLED = "NCRP-2026-104317", "NCRP-2026-470218", "NCRP-2026-258846", "NCRP-2026-582904"
LEAK = ("Example Exchange", "freeze", "hold", "takedown", "KYC", "TW6", "bank", "mule")


@pytest.fixture
def client(tmp_path, monkeypatch):
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ENGINE_MODE", "engine")
    monkeypatch.setenv("CHAINTRACE_MONITOR", "0")
    complaints._tracing.clear()
    complaints._lookups.clear()
    with TestClient(main.app) as c:
        yield c


def trace(c, cid):
    r = c.post(f"/api/officer/complaints/{cid}/trace")
    assert r.status_code == 200, r.text
    return r.json()["case_id"]


def cease(c, case):
    r = c.get(f"/api/officer/cases/{case}/cease")
    assert r.status_code == 200, r.text
    return r.json()


def draft(c, case):
    r = c.post(f"/api/officer/cases/{case}/cease")
    assert r.status_code == 200, r.text
    return r.json()


def stage(c, cid):
    return c.get(f"/api/officer/complaints/{cid}").json()["stage"]


def citizen(c, cid):
    return c.get(f"/api/complaints/{cid}/status").json()


def send(c, rid):
    for step in ("approve", "send"):
        assert c.post(f"/api/officer/requests/{rid}/{step}").status_code == 200


# ---------- the four demo cases ----------
@pytest.mark.parametrize("cid,kind", [(VASP, "vasp"), (DEX, "dex"), (BANK, "bank_account"), (STALLED, "mixer")])
def test_each_demo_case_ends_a_different_way(client, cid, kind):
    case = trace(client, cid)
    kinds = [o["kind"] for o in client.get(f"/api/officer/cases/{case}/outcomes").json()]
    assert kind in kinds


def test_the_demo_cases_are_four_distinct_waiting_complaints(client):
    inbox = {c["complaint_id"]: c for c in client.get("/api/officer/complaints", params={"stage": "received"}).json()}
    for n, cid in enumerate((VASP, DEX, BANK, STALLED)):
        assert cid in inbox and inbox[cid]["description"].startswith("Demo case")
    assert len({inbox[c]["wallet"] for c in (VASP, DEX, BANK, STALLED)}) == 4


def test_the_dex_case_has_nothing_to_freeze_at_the_pool_but_the_site_can_be_taken_down(client):
    items = cease(client, trace(client, DEX))["items"]
    assert items and all(i["kind"] == "takedown_request" for i in items)


def test_the_stalled_case_has_no_freeze_to_send(client):
    assert all(i["kind"] != "freeze_request" for i in cease(client, trace(client, STALLED))["items"])


# ---------- drafting ----------
def test_a_case_with_an_exchange_plans_a_freeze_for_it(client):
    items = cease(client, trace(client, VASP))["items"]
    freeze = [i for i in items if i["kind"] == "freeze_request"]
    assert len(freeze) == 1 and freeze[0]["status"] == "not_drafted" and "Exchange" in freeze[0]["holder"]


def test_the_bank_case_plans_a_bank_freeze_and_an_issuer_hold(client):
    kinds = {i["kind"] for i in cease(client, trace(client, BANK))["items"]}
    assert {"freeze_request", "issuer_hold"} <= kinds


def test_drafting_creates_every_request_once_and_approves_nothing(client):
    case = trace(client, BANK)
    first = draft(client, case)
    assert first["drafts_created"] > 0 and all(i["request_id"] and i["status"] == "draft" for i in first["items"])
    again = draft(client, case)
    assert again["drafts_created"] == 0 and [i["request_id"] for i in again["items"]] == [i["request_id"] for i in first["items"]]
    assert first["started"] is False


def test_drafting_does_not_move_the_complaint(client):
    case = trace(client, BANK)
    draft(client, case)
    assert stage(client, BANK) == "investigating"
    assert citizen(client, BANK)["stage"] == "investigating"


def test_unknown_case_is_404(client):
    assert client.get("/api/officer/cases/C-999/cease").status_code == 404
    assert client.post("/api/officer/cases/C-999/cease").status_code == 404


def test_a_takedown_waits_for_the_preservation_notice(client):
    case = trace(client, DEX)
    item = draft(client, case)["items"][0]
    assert "preservation notice first" in item["note"]
    lead = item["lead_id"]
    pres = client.post(f"/api/officer/cases/{case}/requests", json={"lead_id": lead, "kind": "preservation_notice"}).json()
    send(client, pres["request_id"])
    assert cease(client, case)["items"][0]["note"] is None


# ---------- the stage ----------
def test_sending_the_first_freeze_moves_the_complaint_to_action_initiated(client):
    case = trace(client, VASP)
    rid = next(i["request_id"] for i in draft(client, case)["items"] if i["kind"] == "freeze_request")
    client.post(f"/api/officer/requests/{rid}/approve")
    assert stage(client, VASP) == "investigating"
    client.post(f"/api/officer/requests/{rid}/send")
    assert stage(client, VASP) == "action_initiated"
    status = cease(client, case)
    assert status["started"] is True and status["stage"] == "action_initiated"
    assert status["citizen_sees"] == complaints.MESSAGES["action_initiated"]
    notes = [h["note"] for h in client.get(f"/api/officer/complaints/{VASP}").json()["history"]]
    assert any("SIMULATED" in n for n in notes)


def test_a_request_that_is_not_a_freeze_does_not_move_the_stage(client):
    case = trace(client, VASP)
    lead = next(l for l in client.get(f"/api/officer/cases/{case}/leads").json() if "kyc_request" in l["requests"])
    rid = client.post(f"/api/officer/cases/{case}/requests", json={"lead_id": lead["lead_id"], "kind": "kyc_request"}).json()["request_id"]
    send(client, rid)
    assert stage(client, VASP) == "investigating"


def test_the_citizen_sees_only_the_generic_sentence_after_action(client):
    case = trace(client, VASP)
    for i in draft(client, case)["items"]:
        send(client, i["request_id"])
    view = citizen(client, VASP)
    assert view["stage"] == "action_initiated" and view["message"] == complaints.MESSAGES["action_initiated"]
    assert set(view) == {"complaint_id", "stage", "label", "message", "updated_at", "timeline"}
    text = client.get(f"/api/complaints/{VASP}/status").text
    assert not any(w.lower() in text.lower() for w in ("Example Exchange", "freeze", "KYC", "TDongf", "5000", "SIM-"))
    assert [t["stage"] for t in view["timeline"]][-1] == "action_initiated"


def test_sending_the_exchange_notice_also_moves_the_stage(client):
    case = trace(client, VASP)
    notice = client.get(f"/api/cases/{case}/freeze-notice").json()
    r = client.post("/api/integrations/sahyog/notice", json={**notice, "case_id": case})
    assert r.status_code == 200, r.text
    assert stage(client, VASP) == "action_initiated"


def test_sending_a_second_freeze_does_not_repeat_the_stage_change(client):
    case = trace(client, BANK)
    for i in draft(client, case)["items"]:
        send(client, i["request_id"])
    h = client.get(f"/api/officer/complaints/{BANK}").json()["history"]
    assert [e["stage"] for e in h].count("action_initiated") == 1


# ---------- closing ----------
def test_the_officer_can_close_after_action_and_open_requests_stay_open(client):
    case = trace(client, VASP)
    items = draft(client, case)["items"]
    send(client, items[0]["request_id"])
    r = client.post(f"/api/officer/complaints/{VASP}/close")
    assert r.status_code == 200 and r.json()["stage"] == "closed"
    view = citizen(client, VASP)
    assert view["stage"] == "closed" and "1930" in view["message"]
    reqs = {x["request_id"]: x["status"] for x in client.get(f"/api/officer/cases/{case}/requests").json()}
    assert reqs[items[0]["request_id"]] == "sent"           # closing never closes a request


def test_a_stalled_case_can_be_closed_without_any_action(client):
    trace(client, STALLED)
    assert client.post(f"/api/officer/complaints/{STALLED}/close").json()["stage"] == "closed"


def test_closing_is_refused_before_a_trace_and_twice(client):
    assert client.post(f"/api/officer/complaints/{VASP}/close").status_code == 409
    trace(client, VASP)
    assert client.post(f"/api/officer/complaints/{VASP}/close").status_code == 200
    again = client.post(f"/api/officer/complaints/{VASP}/close")
    assert again.status_code == 409 and "already closed" in again.json()["detail"]
    assert client.post("/api/officer/complaints/NCRP-0-0/close").status_code == 404


def test_a_closed_complaint_is_not_moved_back_by_a_late_send(client):
    case = trace(client, VASP)
    items = draft(client, case)["items"]
    client.post(f"/api/officer/complaints/{VASP}/close")
    send(client, items[0]["request_id"])
    assert stage(client, VASP) == "closed"


# ---------- open or closed on the dashboard ----------
def open_flags(c):
    return {x["case_id"]: x["open"] for x in c.get("/api/cases").json()}


def test_a_case_is_open_until_its_complaint_is_closed(client):
    case = trace(client, VASP)
    assert open_flags(client)[case] is True
    stats = client.get("/api/dashboard").json()
    assert stats["open_cases"] == stats["total_cases"] and stats["closed_cases"] == 0
    client.post(f"/api/officer/complaints/{VASP}/close")
    assert open_flags(client)[case] is False
    stats = client.get("/api/dashboard").json()
    assert stats["closed_cases"] == 1 and stats["open_cases"] + 1 == stats["total_cases"]
    assert [open_flags(client)[c] for c in open_flags(client) if c != case].count(False) == 0
