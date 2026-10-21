"""Investigation 4.3: draft letters, the approval workflow, fictional replies, and the pivot to new identifiers and leads."""
import json

import pytest
from fastapi.testclient import TestClient

from contract.schemas import Alert, InstitutionRequest, Reply
from paths import SEED_COMPLAINTS
from product import alerts, complaints, outreach, personas

SEED = {c["complaint_id"]: c for c in json.loads(SEED_COMPLAINTS.read_text())}
SWEEP, IDLE = "NCRP-2026-104317", "NCRP-2026-258846"


def make_client(tmp_path, monkeypatch, mode, name="t"):
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / f"{name}.db"))
    monkeypatch.setenv("ENGINE_MODE", mode)
    monkeypatch.setenv("CHAINTRACE_MONITOR", "0")
    complaints._tracing.clear()
    return TestClient(main.app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch, "fixture") as c:
        yield c


@pytest.fixture
def engine_client(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch, "engine") as c:
        yield c


@pytest.fixture
def stream():
    q = alerts.subscribe()
    seen = []
    yield lambda: seen.extend(q.get_nowait() for _ in range(q.qsize())) or seen
    alerts.unsubscribe(q)


def case_of(c, cid):
    return c.post(f"/api/officer/complaints/{cid}/trace").json()["case_id"]


def leads(c, case):
    return c.get(f"/api/officer/cases/{case}/leads").json()


def lead_of(c, case, choke_point):
    return next(l for l in leads(c, case) if l["choke_point"] == choke_point)


def draft(c, case, lead, kind=None):
    r = c.post(f"/api/officer/cases/{case}/requests", json={"lead_id": lead["lead_id"], "kind": kind or lead["requests"][0]})
    assert r.status_code == 201, r.text
    return r.json()


def step(c, rid, what):
    return c.post(f"/api/officer/requests/{rid}/{what}")


def run_to_reply(c, rid):
    for what in ("approve", "send", "simulate", "simulate"):
        assert step(c, rid, what).status_code == 200
    return c.get(f"/api/officer/requests/{rid}/reply").json()


# ---- the letter
def all_lead_requests(c, case):
    return [(l, k) for l in leads(c, case) for k in l["requests"]]


def test_every_request_kind_for_every_lead_makes_a_proper_draft(engine_client):
    seen_kinds = set()
    for cid in (SWEEP, IDLE):
        case = case_of(engine_client, cid)
        complaint = SEED[cid]
        for lead, kind in all_lead_requests(engine_client, case):
            r = draft(engine_client, case, lead, kind)
            InstitutionRequest(**r)
            body, subject = r["letter_body"], r["letter_subject"]
            assert r["status"] == "draft" and lead["holder"] in subject and complaint["complaint_id"] in subject
            assert body.startswith("DRAFT FOR OFFICER REVIEW")
            for placeholder in ("[Legal basis", "[Officer name", "[Date of issue]", "[Officer contact details]"):
                assert placeholder in body, (kind, placeholder)
            assert f"{complaint['complaint_id']} / {case}" in body and r["request_id"] in body and r["subject"] in body
            assert lead["holder"] in body and outreach.KIND_LABEL[kind] in body
            for ask in outreach.ASKS[kind]:
                assert ask in body
            assert "None" not in body and "{" not in body
            seen_kinds.add(kind)
    assert len(seen_kinds) >= 8                                                    # almost every kind of request was exercised


def test_a_letter_never_contains_the_victims_personal_details(engine_client):
    for cid in (SWEEP, IDLE):
        case = case_of(engine_client, cid)
        for lead, kind in all_lead_requests(engine_client, case):
            r = draft(engine_client, case, lead, kind)
            text = r["letter_body"] + r["letter_subject"]
            for private in (SEED[cid]["reporter_name"], SEED[cid]["reporter_mobile"], SEED[cid]["state"], SEED[cid]["description"]):
                assert private not in text


def test_the_letter_names_the_identifier_and_the_amount_not_a_person(engine_client):
    case = case_of(engine_client, SWEEP)
    r = draft(engine_client, case, lead_of(engine_client, case, "telecom"), "subscriber_request")
    assert "Phone number: 9000000101" in r["letter_body"] and "about 5,000 USDT" in r["letter_body"]
    bank = draft(engine_client, (c := case_of(engine_client, IDLE)), lead_of(engine_client, c, "bank"), "freeze_request")
    assert "Bank account: 000123450001 (HDFC Bank)" in bank["letter_body"]


def test_each_kind_asks_for_the_right_things(engine_client):
    case = case_of(engine_client, SWEEP)
    pres = draft(engine_client, case, lead_of(engine_client, case, "telecom"), "preservation_notice")["letter_body"]
    assert "Preserve ALL records" in pres and "Do not delete" in pres
    sub = draft(engine_client, case, lead_of(engine_client, case, "telecom"), "subscriber_request")["letter_body"]
    assert "IMEI" in sub and "tower locations" in sub
    kyc = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["letter_body"]
    assert "linked bank accounts" in kyc and "Login IP" in kyc


# ---- creating requests
def test_requests_are_listed_in_order(engine_client):
    case = case_of(engine_client, SWEEP)
    a = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")
    b = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "freeze_request")
    listed = engine_client.get(f"/api/officer/cases/{case}/requests").json()
    assert [r["request_id"] for r in listed] == [a["request_id"], b["request_id"]] == [f"R-{case}-001", f"R-{case}-002"]


def test_a_lead_that_does_not_exist_or_a_kind_it_does_not_have_is_refused(engine_client):
    case = case_of(engine_client, SWEEP)
    lead = lead_of(engine_client, case, "exchange")
    assert engine_client.post(f"/api/officer/cases/{case}/requests", json={"lead_id": "L-nope", "kind": "kyc_request"}).status_code == 422
    r = engine_client.post(f"/api/officer/cases/{case}/requests", json={"lead_id": lead["lead_id"], "kind": "takedown_request"})
    assert r.status_code == 422 and "not one of the requests" in r.json()["detail"]
    assert engine_client.post(f"/api/officer/cases/{case}/requests", json={"lead_id": lead["lead_id"], "kind": "telepathy"}).status_code == 422


def test_the_same_request_cannot_be_drafted_twice(engine_client):
    case = case_of(engine_client, SWEEP)
    lead = lead_of(engine_client, case, "exchange")
    draft(engine_client, case, lead, "kyc_request")
    assert engine_client.post(f"/api/officer/cases/{case}/requests", json={"lead_id": lead["lead_id"], "kind": "kyc_request"}).status_code == 409
    assert len(engine_client.get(f"/api/officer/cases/{case}/requests").json()) == 1


def test_unknown_cases_and_requests_are_404(client):
    assert client.get("/api/officer/cases/C-999/requests").status_code == 404
    assert client.post("/api/officer/cases/C-999/requests", json={"lead_id": "x", "kind": "kyc_request"}).status_code == 404
    for what in ("approve", "send", "simulate", "close"):
        assert step(client, "R-NOPE", what).status_code == 404
    assert client.get("/api/officer/requests/R-NOPE").status_code == 404 and client.get("/api/officer/requests/R-NOPE/reply").status_code == 404


# ---- the approval workflow
def test_a_request_goes_through_every_stage_in_order(engine_client):
    case = case_of(engine_client, SWEEP)
    rid = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"]
    seen = ["draft"]
    for what in ("approve", "send", "simulate", "simulate", "close"):
        r = step(engine_client, rid, what).json()
        seen.append(r["status"])
    assert seen == ["draft", "approved", "sent", "acknowledged", "replied", "closed"]
    final = engine_client.get(f"/api/officer/requests/{rid}").json()
    assert [h["status"] for h in final["history"]] == seen
    assert "SIMULATED" in final["history"][2]["note"] and "demo: no login" in final["history"][1]["note"]


def test_nothing_can_be_sent_without_an_officers_approval(engine_client):
    case = case_of(engine_client, SWEEP)
    rid = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"]
    r = step(engine_client, rid, "send")
    assert r.status_code == 409 and "cannot go to sent" in r.json()["detail"]
    assert engine_client.get(f"/api/officer/requests/{rid}").json()["status"] == "draft"
    assert step(engine_client, rid, "simulate").status_code == 409                 # no demo reply for a draft either


@pytest.mark.parametrize("path,fails_when", [
    (["approve", "approve"], "second approve"), (["approve", "send", "approve"], "approve after send"),
    (["approve", "send", "send"], "send twice"), (["approve", "close"], "close before it was sent"), (["close"], "close a draft"),
])
def test_out_of_order_moves_are_refused(engine_client, path, fails_when):
    case = case_of(engine_client, SWEEP)
    rid = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"]
    codes = [step(engine_client, rid, w).status_code for w in path]
    assert codes[-1] == 409, fails_when


def test_a_replied_request_cannot_be_simulated_again_but_can_be_closed(engine_client):
    case = case_of(engine_client, SWEEP)
    rid = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"]
    run_to_reply(engine_client, rid)
    assert step(engine_client, rid, "simulate").status_code == 409
    assert step(engine_client, rid, "close").status_code == 200
    assert step(engine_client, rid, "close").status_code == 409


def test_a_request_can_be_closed_while_waiting(engine_client):
    case = case_of(engine_client, SWEEP)
    rid = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"]
    step(engine_client, rid, "approve"); step(engine_client, rid, "send")
    assert step(engine_client, rid, "close").json()["status"] == "closed"


def test_the_acknowledgement_reference_is_set_when_sent_and_stable(engine_client):
    case = case_of(engine_client, SWEEP)
    rid = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"]
    assert engine_client.get(f"/api/officer/requests/{rid}").json()["reference"] is None
    step(engine_client, rid, "approve")
    ref = step(engine_client, rid, "send").json()["reference"]
    assert ref.startswith("SIM-") and step(engine_client, rid, "simulate").json()["reference"] == ref


# ---- replies
def test_there_is_no_reply_until_the_institution_answers(engine_client):
    case = case_of(engine_client, SWEEP)
    rid = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"]
    assert engine_client.get(f"/api/officer/requests/{rid}/reply").status_code == 404
    for what in ("approve", "send", "simulate"):
        step(engine_client, rid, what)
    assert engine_client.get(f"/api/officer/requests/{rid}/reply").status_code == 404           # acknowledged, not yet answered


@pytest.mark.parametrize("cid", [SWEEP, IDLE])
def test_every_kind_of_request_gets_a_fictional_reply(engine_client, cid):
    case = case_of(engine_client, cid)
    n = 0
    for lead, kind in all_lead_requests(engine_client, case):
        rid = draft(engine_client, case, lead, kind)["request_id"]
        reply = Reply(**run_to_reply(engine_client, rid))
        assert reply.fictional is True and reply.fields and reply.summary
        assert reply.request_id == rid and reply.case_id == case and reply.reply_id == f"P-{rid}"
        text = json.dumps([f.model_dump() for f in reply.fields])
        assert "demo" in text.lower() or kind in ("preservation_notice", "freeze_request", "issuer_hold", "takedown_request")
        n += 1
    assert n >= 10


def test_a_freeze_or_hold_reply_confirms_the_amount_held(engine_client):
    case = case_of(engine_client, SWEEP)
    freeze = Reply(**run_to_reply(engine_client, draft(engine_client, case, lead_of(engine_client, case, "exchange"), "freeze_request")["request_id"]))
    fields = {f.label: f.value for f in freeze.fields}
    assert fields["Status"] == "Account frozen" and fields["Amount held"] == "4,950 USDT" and fields["Reference"].startswith("REF-")
    assert freeze.new_identifier_ids == []                                           # a freeze teaches us nothing new about people
    pres = Reply(**run_to_reply(engine_client, draft(engine_client, case, lead_of(engine_client, case, "exchange"), "preservation_notice")["request_id"]))
    assert {f.label: f.value for f in pres.fields}["Status"] == "Records preserved for 180 days"


def test_the_replies_are_marked_as_simulated_in_the_alert_and_history(engine_client, stream):
    case = case_of(engine_client, SWEEP)
    rid = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"]
    run_to_reply(engine_client, rid)
    a = next(x for x in stream() if x["type"] == "REPLY_RECEIVED")
    Alert(**a)
    assert a["case_id"] == case and "(simulated)" in a["message"] and "Example Exchange B" in a["message"] and "5 new identifier(s)" in a["message"]


# ---- the pivot: a reply adds identifiers, which open new leads
def test_an_exchange_kyc_reply_adds_a_person_a_mule_account_and_more(engine_client):
    case = case_of(engine_client, SWEEP)
    before = {i["identifier_id"] for i in engine_client.get(f"/api/officer/cases/{case}/identifiers").json()}
    rid = draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"]
    reply = run_to_reply(engine_client, rid)
    items = engine_client.get(f"/api/officer/cases/{case}/identifiers").json()
    added = [i for i in items if i["identifier_id"] not in before]
    assert {i["identifier_id"] for i in added} == set(reply["new_identifier_ids"])
    assert sorted(i["kind"] for i in added) == ["bank_account", "device", "email", "ip_address", "phone"]
    assert all(i["source"] == "reply" and i["source_ref"] == rid and i["confidence"] == 0.8 for i in added)
    assert next(i for i in added if i["kind"] == "bank_account")["role"] == "mule_suspect"


def test_new_identifiers_open_new_leads(engine_client):
    case = case_of(engine_client, SWEEP)
    before = {l["lead_id"] for l in leads(engine_client, case)}
    run_to_reply(engine_client, draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"])
    new = [l for l in leads(engine_client, case) if l["lead_id"] not in before]
    assert {l["choke_point"] for l in new} >= {"telecom", "bank", "messaging_platform"}                 # the new phone and the mule account
    assert len(new) >= 3


def test_following_the_new_leads_goes_on_to_a_second_round(engine_client):
    case = case_of(engine_client, SWEEP)
    run_to_reply(engine_client, draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"])
    mule = next(l for l in leads(engine_client, case) if l["choke_point"] == "bank")
    reply = run_to_reply(engine_client, draft(engine_client, case, mule, "account_details_request")["request_id"])
    fields = {f["label"]: f["value"] for f in reply["fields"]}
    assert "(demo" in fields["Account holder"] and fields["Registered mobile"] == "9000000513"      # the mule account was set up with the operator's second SIM
    assert "Money moved on to" in fields
    assert any(i["kind"] == "bank_account" for i in engine_client.get(f"/api/officer/cases/{case}/identifiers").json() if i["source"] == "reply" and i["source_ref"].endswith("002"))


def test_a_reply_adds_nothing_twice(engine_client):
    case = case_of(engine_client, SWEEP)
    lead = lead_of(engine_client, case, "exchange")
    run_to_reply(engine_client, draft(engine_client, case, lead, "kyc_request")["request_id"])
    n = len(engine_client.get(f"/api/officer/cases/{case}/identifiers").json())
    again = Reply(**run_to_reply(engine_client, draft(engine_client, case, lead, "account_details_request")["request_id"])) if "account_details_request" in lead["requests"] else None
    assert again is None or len(engine_client.get(f"/api/officer/cases/{case}/identifiers").json()) == n


def test_the_mule_account_from_a_reply_shows_in_the_outcomes_and_mules(engine_client):
    case = case_of(engine_client, SWEEP)
    run_to_reply(engine_client, draft(engine_client, case, lead_of(engine_client, case, "exchange"), "kyc_request")["request_id"])
    assert any(o["kind"] == "bank_account" for o in engine_client.get(f"/api/officer/cases/{case}/outcomes").json())
    assert any(m["kind"] == "bank_account" and "State Bank of India" == m["label"] for m in engine_client.get(f"/api/officer/cases/{case}/mules").json())


# ---- shared personas: the same person behind several cases (what 4.4 links on)
def reply_fields(c, case, choke_point="exchange"):
    lead = lead_of(c, case, choke_point)
    reply = run_to_reply(c, draft(c, case, lead, "kyc_request" if choke_point == "exchange" else lead["requests"][0])["request_id"])
    return {f["label"]: f["value"] for f in reply["fields"]}


def test_cases_of_one_operation_get_the_same_person_in_their_replies(client):
    a, b = reply_fields(client, "C-001"), reply_fields(client, "C-002")
    for key in ("Account holder", "Registered mobile", "Registered email", "Device", "Recent login IPs"):
        assert a[key] == b[key], key
    assert a["Account holder"] == "Anil Varkey (demo)"


def test_different_operations_get_different_people(client):
    hero, sextortion = reply_fields(client, "C-001"), reply_fields(client, "C-004")
    assert hero["Account holder"] != sextortion["Account holder"] and hero["Registered mobile"] != sextortion["Registered mobile"]
    assert sextortion["Account holder"] == "Rohan Dsouza (demo)"
    assert reply_fields(client, "C-005")["Registered mobile"] == sextortion["Registered mobile"]


def test_the_mule_accounts_name_a_holder_who_is_not_the_operator(client):
    case = "C-001"
    run_to_reply(client, draft(client, case, lead_of(client, case, "exchange"), "kyc_request")["request_id"])
    bank = reply_fields(client, case, "bank")
    assert bank["Account holder"].startswith("Kiran Pillai (demo")
    assert bank["Registered mobile"] == "9000000511"                          # but the mule account was set up with the operator's second SIM


def test_replies_are_reproducible(tmp_path, monkeypatch):
    out = []
    for name in ("a", "b"):
        with make_client(tmp_path, monkeypatch, "fixture", name) as c:
            out.append(reply_fields(c, "C-001"))
    assert out[0] == out[1]


def test_personas_are_obviously_fictional():
    for p in personas.PERSONAS:
        assert "(demo)" in p["name"] and p["phone"].startswith("90000") and p["email"].endswith("mail.example")
    assert personas.persona_for(["Hero-Invest.Example"], "x") is personas.PERSONAS[0]
    assert personas.persona_for(["nothing special"], "seed") in personas.PERSONAS


# ---- persistence and the API surface
def test_requests_and_replies_survive_a_restart(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch, "fixture", "keep") as c:
        rid = draft(c, "C-001", lead_of(c, "C-001", "exchange"), "kyc_request")["request_id"]
        run_to_reply(c, rid)
    with make_client(tmp_path, monkeypatch, "fixture", "keep") as c:
        assert c.get(f"/api/officer/requests/{rid}").json()["status"] == "replied"
        assert c.get(f"/api/officer/requests/{rid}/reply").json()["fictional"] is True


def test_openapi_lists_the_request_routes():
    import main
    paths = main.app.openapi()["paths"]
    for p in ("/api/officer/cases/{case_id}/requests", "/api/officer/requests/{request_id}", "/api/officer/requests/{request_id}/approve",
              "/api/officer/requests/{request_id}/send", "/api/officer/requests/{request_id}/simulate",
              "/api/officer/requests/{request_id}/close", "/api/officer/requests/{request_id}/reply"):
        assert p in paths
