"""Investigation 4.4: linking cases, naming suspected people from replies, the demo run, the dossier and the referral."""
import json
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from contract.schemas import CasePeople, PersonCluster, Referral
from paths import SCENARIOS, SCENARIOS_JSON
from product import complaints, dossier, people, store

REAL = json.loads((SCENARIOS / "real_case.json").read_text())
SCEN = {s["key"]: s for s in json.loads(SCENARIOS_JSON.read_text())}
HERO = ["C-001", "C-002", "C-003"]


def make_client(tmp_path, monkeypatch, mode="fixture", name="t"):
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / f"{name}.db"))
    monkeypatch.setenv("ENGINE_MODE", mode)
    monkeypatch.setenv("CHAINTRACE_MONITOR", "0")
    complaints._tracing.clear()
    return TestClient(main.app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        yield c


@pytest.fixture
def engine_client(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch, "engine", "e") as c:
        yield c


def clusters(c):
    return {x["cluster_id"]: PersonCluster(**x) for x in c.get("/api/officer/clusters").json()}


def demo(c, case, rounds=2):
    r = c.post(f"/api/officer/cases/{case}/demo-run", params={"rounds": rounds})
    assert r.status_code == 200
    return r.json()


def add_id(c, case, kind, value, role="other"):
    assert c.post(f"/api/officer/cases/{case}/identifiers", json={"kind": kind, "value": value, "role": role}).status_code == 201


# ---- linking cases by shared identifiers
def test_the_seeded_operations_are_linked_before_any_reply(client):
    cl = clusters(client)
    assert set(cl) == {"CL-C-001", "CL-C-004"}
    hero, sext = cl["CL-C-001"], cl["CL-C-004"]
    assert hero.case_ids == HERO and hero.complaint_ids == [f"NCRP-2026-000{i}" for i in (1, 2, 3)]
    assert hero.total_lost == 26300.0 and hero.states == ["Delhi", "Karnataka", "Maharashtra"] and hero.people == []
    assert sext.case_ids == ["C-004", "C-005"] and sext.total_lost == 4000.0
    assert "no institution has yet named a person" in hero.summary and "shared identifier" in hero.summary
    assert hero.caution.startswith("These links and names are inferences") and "victims too" in hero.caution


def test_each_shared_identifier_says_how_strong_a_link_it_is_and_which_cases_share_it(client):
    by = {(s.kind, s.value): s for s in clusters(client)["CL-C-001"].shared}
    assert by[("domain", "hero-invest.example")].case_ids == HERO and by[("domain", "hero-invest.example")].strength == "strong"
    assert by[("upi_id", "hero.invest@okaxis")].case_ids == ["C-001", "C-002"]
    assert by[("phone", "9000000201")].case_ids == ["C-003"] if ("phone", "9000000201") in by else True
    sext = {(s.kind, s.value): s for s in clusters(client)["CL-C-004"].shared}
    assert sext[("social_handle", "private_pics_demo")].case_ids == ["C-004", "C-005"]


def test_unrelated_cases_are_not_linked(client):
    for case in ("C-006", "C-007", "C-008"):
        p = CasePeople(**client.get(f"/api/officer/cases/{case}/people").json())
        assert p.cluster is None and p.people == []


def test_one_ip_address_alone_does_not_link_two_cases(client):
    add_id(client, "C-006", "ip_address", "203.0.113.200")
    add_id(client, "C-007", "ip_address", "203.0.113.200")
    assert "CL-C-006" not in clusters(client)


def test_two_weaker_shared_identifiers_do_link(client):
    for case in ("C-006", "C-007"):
        add_id(client, case, "ip_address", "203.0.113.201")
        add_id(client, case, "app", "SameApp")
    assert clusters(client)["CL-C-006"].case_ids == ["C-006", "C-007"]


def test_one_strong_identifier_links(client):
    add_id(client, "C-006", "phone", "+91 90000 99999")
    add_id(client, "C-007", "phone", "9000099999")                                    # written differently: still the same phone
    cl = clusters(client)["CL-C-006"]
    assert cl.case_ids == ["C-006", "C-007"] and cl.shared[0].strength == "strong" and cl.shared[0].value == "9000099999"


def test_a_wallet_that_merely_holds_funds_does_not_link_cases(client):
    add_id(client, "C-006", "wallet", "TSharedIdleHolderxxxxxxxxxxxxxxxxxxx", role="other")
    add_id(client, "C-007", "wallet", "TSharedIdleHolderxxxxxxxxxxxxxxxxxxx", role="other")
    assert "CL-C-006" not in clusters(client)
    add_id(client, "C-006", "wallet", "TSharedMulexxxxxxxxxxxxxxxxxxxxxxxxxx", role="mule_suspect")
    add_id(client, "C-007", "wallet", "TSharedMulexxxxxxxxxxxxxxxxxxxxxxxxxx", role="mule_suspect")
    assert "CL-C-006" in clusters(client)


def test_clusters_merge_when_a_new_shared_identifier_bridges_them(client):
    add_id(client, "C-003", "email", "bridge@mail.example")
    add_id(client, "C-004", "email", "bridge@mail.example")
    cl = clusters(client)
    assert set(cl) == {"CL-C-001"} and cl["CL-C-001"].case_ids == HERO + ["C-004", "C-005"]


def test_strength_by_kind():
    assert [people.strength(k) for k in ("phone", "email", "device", "domain", "upi_id", "social_handle", "bank_account", "wallet", "ip_address", "app")] == \
        ["strong"] * 8 + ["moderate", "weak"]


# ---- naming people, from replies only
def test_a_person_is_named_only_after_institutions_reply(client):
    assert client.get("/api/officer/cases/C-001/people").json()["people"] == []
    demo(client, "C-001")
    names = [p["name"] for p in client.get("/api/officer/cases/C-001/people").json()["people"]]
    assert "Anil Varkey (demo)" in names


def test_the_same_person_across_cases_and_institutions_raises_the_suspicion(client):
    one = client.post("/api/officer/cases/C-001/demo-run", params={"rounds": 1}).json()
    assert one["replies"] > 0
    first = next(p for p in client.get("/api/officer/cases/C-001/people").json()["people"] if p["role"] == "operator_suspected")
    for case in ("C-002", "C-003"):
        demo(client, case)
    hero = clusters(client)["CL-C-001"]
    op = next(p for p in hero.people if p.role == "operator_suspected")
    assert op.name == "Anil Varkey (demo)" and op.case_ids == HERO
    assert len({e.institution for e in op.evidence}) >= 3 and op.confidence > first["confidence"]
    assert op.confidence <= people.MAX_OPERATOR_CONFIDENCE and "institutions in 3 cases" in op.basis
    assert "appears in the replies of 3 of them" in hero.summary


def test_a_single_reply_in_a_single_case_stays_low(client):
    leads = client.get("/api/officer/cases/C-001/leads").json()
    lead = next(l for l in leads if l["choke_point"] == "exchange")
    rid = client.post("/api/officer/cases/C-001/requests", json={"lead_id": lead["lead_id"], "kind": "kyc_request"}).json()["request_id"]
    for what in ("approve", "send", "simulate", "simulate"):
        client.post(f"/api/officer/requests/{rid}/{what}")
    op = next(p for p in client.get("/api/officer/cases/C-001/people").json()["people"] if p["role"] == "operator_suspected")
    assert op["confidence"] == 0.35 and op["basis"] == "Named by 1 institution in 1 case"


def test_every_name_comes_with_the_exact_reply_it_came_from(client):
    demo(client, "C-001")
    people_ = client.get("/api/officer/cases/C-001/people").json()["people"]
    for p in people_:
        assert p["evidence"]
        for e in p["evidence"]:
            req = client.get(f"/api/officer/requests/{e['request_id']}").json()
            reply = client.get(f"/api/officer/requests/{e['request_id']}/reply").json()
            assert req["holder"] == e["institution"] and e["case_id"] == "C-001"
            assert {f["label"]: f["value"] for f in reply["fields"]}[e["field"]] == e["value"] == p["name"]


def test_the_operators_phone_email_and_device_are_tied_to_them(client):
    demo(client, "C-001")
    op = next(p for p in client.get("/api/officer/cases/C-001/people").json()["people"] if p["role"] == "operator_suspected")
    assert {"phone: 9000000501", "email: anil.v.demo@mail.example", "device: imei-35000000000501"} <= set(op["identifiers"])
    assert not any(i.startswith(("bank_account", "wallet")) for i in op["identifiers"])


def test_holders_of_mule_accounts_are_listed_apart_at_low_confidence_with_a_caution(client):
    demo(client, "C-001")
    people_ = client.get("/api/officer/cases/C-001/people").json()["people"]
    mules = [p for p in people_ if p["role"] == "mule_holder"]
    assert mules and all(p["confidence"] == people.MULE_CONFIDENCE and "victim" in p["basis"] for p in mules)
    assert people_[0]["role"] == "operator_suspected"                                 # operators come first
    assert not any(p["name"] == mules[0]["name"] for p in people_ if p["role"] == "operator_suspected")


def test_different_operations_get_different_people(client):
    for case in HERO + ["C-004", "C-005"]:
        demo(client, case)
    cl = clusters(client)
    hero_op = next(p for p in cl["CL-C-001"].people if p.role == "operator_suspected")
    sext_op = next(p for p in cl["CL-C-004"].people if p.role == "operator_suspected")
    assert hero_op.name != sext_op.name and set(hero_op.identifiers).isdisjoint(sext_op.identifiers)


def test_nothing_says_anyone_is_guilty(client):
    for case in HERO:
        demo(client, case)
    text = json.dumps(client.get("/api/officer/clusters").json()).lower()
    for word in ("guilty", "convicted", "criminal", "confirmed", "arrest"):
        assert word not in text


# ---- the demo run
def test_the_demo_run_works_through_every_lead_and_leaves_replies(client):
    r = demo(client, "C-001", rounds=1)
    assert r["requests"] == r["replies"] and r["requests"] >= 3 and r["new_identifiers"] >= r["replies"]
    reqs = client.get("/api/officer/cases/C-001/requests").json()
    assert len(reqs) == r["requests"] and {x["status"] for x in reqs} == {"replied"}
    assert all([h["status"] for h in x["history"]] == ["draft", "approved", "sent", "acknowledged", "replied"] for x in reqs)


def test_more_rounds_follow_the_new_leads_and_it_stops_when_there_is_nothing_left(client):
    one = demo(client, "C-001", rounds=1)
    two = demo(client, "C-001", rounds=3)
    assert two["requests"] > 0
    assert demo(client, "C-001", rounds=3) == {"requests": 0, "replies": 0, "new_identifiers": 0}
    assert len(client.get("/api/officer/cases/C-001/requests").json()) == one["requests"] + two["requests"]


def test_the_demo_run_never_sends_an_unapproved_letter(client):
    demo(client, "C-001")
    for r in client.get("/api/officer/cases/C-001/requests").json():
        statuses = [h["status"] for h in r["history"]]
        assert statuses.index("approved") < statuses.index("sent")


def test_the_demo_run_rejects_bad_input(client):
    assert client.post("/api/officer/cases/C-001/demo-run", params={"rounds": 0}).status_code == 422
    assert client.post("/api/officer/cases/C-001/demo-run", params={"rounds": 9}).status_code == 422
    assert client.post("/api/officer/cases/C-999/demo-run").status_code == 404


# ---- the dossier
def pdf(c, case):
    r = c.get(f"/api/officer/cases/{case}/dossier")
    assert r.status_code == 200
    return r


def pdf_text(content, tmp_path):
    f = tmp_path / "d.pdf"
    f.write_bytes(content)
    return subprocess.run(["pdftotext", "-layout", str(f), "-"], capture_output=True, text=True).stdout


needs_pdftotext = pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext is not installed")


def test_the_dossier_is_a_pdf_that_is_never_cached(client):
    r = pdf(client, "C-001")
    assert r.content[:5] == b"%PDF-" and len(r.content) > 5000
    assert r.headers["content-type"] == "application/pdf" and r.headers["cache-control"] == "no-store"
    assert 'filename="C-001_referral_dossier.pdf"' in r.headers["content-disposition"]
    assert client.get("/api/officer/cases/C-999/dossier").status_code == 404


@needs_pdftotext
def test_the_dossier_has_every_section_and_the_cautions(client, tmp_path):
    for case in HERO:
        demo(client, case)
    text = pdf_text(pdf(client, "C-001").content, tmp_path)
    for heading in ("Referral dossier", "1. Where the money went", "2. Fund-flow graph", "3. Suspected mules", "4. Identifiers",
                    "5. Requests and replies", "6. Linked cases and suspected people", "7. Evidence checklist", "8. Limits and cautions"):
        assert heading in text, heading
    assert "Anil Varkey (demo)" in text and "FICTIONAL DEMO DATA" in text and "SHA-256 (dossier data)" in text
    assert "Any arrest, search, seizure or other legal action is for the investigating agency" in text
    assert "Nothing here says that anyone is guilty" in text.replace("\n", " ").replace("  ", " ")
    for part in ("Records: what an institution or the chain told us", "Inferences: our reading", "Still missing"):
        assert part in text


@needs_pdftotext
def test_the_dossier_never_contains_the_victims_personal_details(client, tmp_path):
    seed = {c["complaint_id"]: c for c in json.loads((SCENARIOS.parent / "seed" / "seed_complaints.json").read_text())}["NCRP-2026-0001"]
    demo(client, "C-001")
    text = pdf_text(pdf(client, "C-001").content, tmp_path)
    assert seed["reporter_name"] not in text and seed["reporter_mobile"] not in text
    assert "not part of this dossier" in text
    assert seed["reporter_name"] not in json.dumps(dossier.data("C-001"))


def test_the_checklist_separates_records_inferences_and_what_is_missing(client):
    before = dossier.checklist("C-001", dossier.data("C-001"))
    assert before["records"] == ["On-chain transfers: 10 transfers between 11 wallets (SIMULATED data)."]
    assert any("No request yet to" in m for m in before["missing"]) and "No institution has yet named a person behind this case." in before["missing"]
    assert any(i.startswith("Exchange attribution") for i in before["inferences"])
    demo(client, "C-001")
    after = dossier.checklist("C-001", dossier.data("C-001"))
    assert any("[FICTIONAL in this demo]" in r for r in after["records"]) and len(after["records"]) > 1
    assert any("Anil Varkey (demo)" in i for i in after["inferences"])
    assert "No institution has yet named a person behind this case." not in after["missing"]


def test_a_request_still_waiting_is_listed_as_missing(client):
    lead = next(l for l in client.get("/api/officer/cases/C-001/leads").json() if l["choke_point"] == "exchange")
    rid = client.post("/api/officer/cases/C-001/requests", json={"lead_id": lead["lead_id"], "kind": "kyc_request"}).json()["request_id"]
    assert f"Request {rid} to Example Exchange A is draft: no reply yet." in dossier.checklist("C-001", dossier.data("C-001"))["missing"]


def test_the_dossier_hash_is_stable_and_changes_when_the_case_changes(client):
    a, b = dossier.dossier_hash(dossier.data("C-001")), dossier.dossier_hash(dossier.data("C-001"))
    assert a == b and len(a) == 64
    demo(client, "C-001")
    assert dossier.dossier_hash(dossier.data("C-001")) != a


def test_the_dossier_works_for_a_dex_case_and_so_does_the_evidence_report(engine_client):
    cid = engine_client.post("/api/complaints", json={"wallet": SCEN["dex"]["wallet"], "amount": 4000, "reporter_name": "D", "reporter_mobile": "9811122233"}).json()["complaint_id"]
    case = engine_client.post(f"/api/officer/complaints/{cid}/trace").json()["case_id"]
    assert pdf(engine_client, case).content[:5] == b"%PDF-"
    report = engine_client.get(f"/api/cases/{case}/report")                       # this crashed on a DEX node before
    assert report.status_code == 200 and report.content[:5] == b"%PDF-"


def test_the_dossier_works_for_every_seeded_case_and_the_real_flow(client, engine_client):
    for c in client.get("/api/cases").json():
        assert pdf(client, c["case_id"]).content[:5] == b"%PDF-"
    cid = engine_client.post("/api/complaints", json={"wallet": REAL["wallet"], "amount": REAL["amount"], "reporter_name": "R", "reporter_mobile": "9811122233"}).json()["complaint_id"]
    case = engine_client.post(f"/api/officer/complaints/{cid}/trace").json()["case_id"]
    demo(engine_client, case)
    assert pdf(engine_client, case).content[:5] == b"%PDF-"


# ---- the referral
def test_a_case_can_be_referred_once_with_the_dossier_hash_as_it_stood(client):
    assert client.get("/api/officer/cases/C-001/referral").status_code == 404
    demo(client, "C-001")
    expected = dossier.dossier_hash(dossier.data("C-001"))
    r = client.post("/api/officer/cases/C-001/referral", json={"agency": "  Cyber Crime Cell (demo) ", "note": "First referral"})
    assert r.status_code == 201
    ref = Referral(**r.json())
    assert ref.agency == "Cyber Crime Cell (demo)" and ref.dossier_sha256 == expected and ref.status == "referred" and ref.note == "First referral"
    assert client.get("/api/officer/cases/C-001/referral").json() == r.json()
    assert client.post("/api/officer/cases/C-001/referral", json={"agency": "Another"}).status_code == 409


@pytest.mark.parametrize("body", [{"agency": ""}, {}, {"agency": "x" * 121}, {"agency": "A", "note": "n" * 1001}])
def test_a_bad_referral_is_refused(client, body):
    assert client.post("/api/officer/cases/C-001/referral", json=body).status_code == 422
    assert client.get("/api/officer/cases/C-001/referral").status_code == 404


def test_referral_routes_404_for_an_unknown_case(client):
    assert client.get("/api/officer/cases/C-999/referral").status_code == 404
    assert client.post("/api/officer/cases/C-999/referral", json={"agency": "A"}).status_code == 404


def test_the_referral_survives_a_restart(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch, name="keep") as c:
        c.post("/api/officer/cases/C-004/referral", json={"agency": "Agency (demo)"})
    with make_client(tmp_path, monkeypatch, name="keep") as c:
        assert c.get("/api/officer/cases/C-004/referral").json()["agency"] == "Agency (demo)"


def test_openapi_lists_the_new_routes():
    import main
    paths = main.app.openapi()["paths"]
    for p in ("/api/officer/clusters", "/api/officer/cases/{case_id}/people", "/api/officer/cases/{case_id}/demo-run",
              "/api/officer/cases/{case_id}/dossier", "/api/officer/cases/{case_id}/referral"):
        assert p in paths
