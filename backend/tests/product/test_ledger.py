"""Investigation 4.1: the identifier ledger, the leads rules, the lure channels on intake, and the officer routes."""
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from contract.schemas import ComplaintRequest, Identifier, Lead
from paths import SEED_COMPLAINTS
from product import complaints, ledger, store

SEED = {c["complaint_id"]: c for c in json.loads(SEED_COMPLAINTS.read_text())}
SWEEP, IDLE, REAL = "NCRP-2026-104317", "NCRP-2026-258846", "NCRP-2026-391502"
GOOD = {"wallet": "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo", "reporter_name": "Test", "reporter_mobile": "9876543210"}


def make_client(tmp_path, monkeypatch, mode):
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / f"{mode}.db"))
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


def traced(c, cid):
    return c.post(f"/api/officer/complaints/{cid}/trace").json()["case_id"]


def by_kind(items, kind):
    return [i for i in items if i["kind"] == kind]


# ---- normalising
@pytest.mark.parametrize("kind,raw,clean", [
    ("phone", "+91 98765-43210", "9876543210"), ("phone", "(098) 7654 3210", "9876543210"), ("phone", "12345", "12345"),
    ("domain", "https://www.Fake-Trade.com/login?x=1", "fake-trade.com"), ("domain", "FAKE.com:8080/x", "fake.com"),
    ("domain", "http://sub.site.example", "sub.site.example"),
    ("social_handle", "@Scam_User", "scam_user"), ("social_handle", "  scam_user ", "scam_user"),
    ("upi_id", " Scam@YBL ", "scam@ybl"), ("email", "A@B.com", "a@b.com"), ("bank_account", "1234 5678-90", "1234567890"),
    ("wallet", "0xABCdef", "0xabcdef"), ("wallet", "TAbC", "TAbC"), ("app", "  My   App ", "My App"), ("ip_address", "10.0.0.1", "10.0.0.1"),
])
def test_normalising_makes_the_same_thing_look_the_same(kind, raw, clean):
    assert ledger.normalize(kind, raw) == clean


@pytest.mark.parametrize("kind,raw", [("phone", "   "), ("domain", "https://"), ("social_handle", "@"), ("bank_account", "abc"), ("app", "")])
def test_nothing_normalises_to_nothing(kind, raw):
    with pytest.raises(ValueError):
        ledger.normalize(kind, raw)


def test_banks_and_upi_apps_are_hints_from_the_code():
    assert ledger.bank_of("HDFC0000001") == "HDFC Bank" and ledger.bank_of("sbin0001") == "State Bank of India"
    assert ledger.bank_of("ZZZZ0000001") is None and ledger.bank_of(None) is None
    assert ledger.upi_app("x@ybl") == "PhonePe" and ledger.upi_app("x@OKAXIS") == "Google Pay" and ledger.upi_app("x@unknownbank") is None


# ---- the lure channels on intake
def test_every_lure_channel_is_optional():
    assert ComplaintRequest(**GOOD).scammer_phone is None


@pytest.mark.parametrize("over", [
    {"scammer_phone": "abc"}, {"scammer_phone": "1"}, {"scammer_phone": "9" * 30}, {"paid_to_upi": "no-at-sign"}, {"paid_to_upi": "@ybl"},
    {"paid_to_bank_account": "12ab"}, {"paid_to_bank_account": "1" * 25}, {"paid_to_ifsc": "BAD"}, {"paid_to_ifsc": "SBIN1000001"},
    {"scammer_handle_platform": "myspace"}, {"scam_website": "x" * 301}, {"scammer_handle": "y" * 81}, {"scam_app": "z" * 121},
])
def test_bad_lure_channels_are_rejected(over):
    with pytest.raises(ValidationError):
        ComplaintRequest(**GOOD, **over)


def test_lure_channels_are_kept_for_officers_and_never_shown_to_the_citizen(client):
    body = {**GOOD, "scammer_phone": "+91 90000 00999", "scammer_handle": "@x_demo", "scammer_handle_platform": "telegram",
            "scam_website": "bad.example", "scam_app": "BadApp", "paid_to_upi": "bad@ybl", "paid_to_bank_account": "000999",
            "paid_to_ifsc": "SBIN0000001"}
    r = client.post("/api/complaints", json=body)
    assert r.status_code == 201
    cid = r.json()["complaint_id"]
    officer = client.get(f"/api/officer/complaints/{cid}").json()
    assert officer["paid_to_upi"] == "bad@ybl" and officer["scammer_handle_platform"] == "telegram" and officer["paid_to_ifsc"] == "SBIN0000001"
    public = client.get(f"/api/complaints/{cid}/status").text.lower() + r.text.lower()
    for secret in ("bad@ybl", "bad.example", "badapp", "x_demo", "000999", "90000", "sbin"):
        assert secret not in public


def test_a_bad_channel_rejects_the_whole_complaint(client):
    n = len(client.get("/api/officer/complaints").json())
    assert client.post("/api/complaints", json={**GOOD, "paid_to_upi": "nope"}).status_code == 422
    assert len(client.get("/api/officer/complaints").json()) == n


# ---- the ledger built from a complaint and a trace
def test_a_traced_complaint_gets_its_ledger(engine_client):
    case = traced(engine_client, SWEEP)
    items = engine_client.get(f"/api/officer/cases/{case}/identifiers").json()
    Identifier(**items[0])
    kinds = sorted(i["kind"] for i in items)
    assert {"wallet", "phone", "social_handle", "domain", "upi_id"} <= set(kinds)
    wallet = by_kind(items, "wallet")
    assert next(i for i in wallet if i["role"] == "reported")["value"] == SEED[SWEEP]["wallet"]
    deposit = next(i for i in wallet if i["role"] == "vasp_deposit")
    assert deposit["label"].startswith("Example Exchange B") and deposit["source"] == "trace" and 0 < deposit["confidence"] < 0.9


def test_the_victims_reported_details_are_marked_as_unchecked(engine_client):
    items = engine_client.get(f"/api/officer/cases/{traced(engine_client, SWEEP)}/identifiers").json()
    phone = by_kind(items, "phone")[0]
    assert (phone["value"], phone["role"], phone["source"], phone["source_ref"], phone["confidence"]) == ("9000000101", "lure", "complaint", SWEEP, 0.5)
    handle = by_kind(items, "social_handle")[0]
    assert (handle["value"], handle["label"]) == ("alpha_returns_demo", "Telegram")                  # @ removed, platform kept
    assert by_kind(items, "upi_id")[0]["label"] == "PhonePe" and by_kind(items, "domain")[0]["value"] == "alpha-returns.example"


def test_bank_details_name_the_bank_from_the_ifsc(engine_client):
    items = engine_client.get(f"/api/officer/cases/{traced(engine_client, IDLE)}/identifiers").json()
    bank = by_kind(items, "bank_account")[0]
    assert (bank["value"], bank["label"], bank["role"]) == ("000123450001", "HDFC Bank", "payment")
    assert by_kind(items, "app")[0]["value"] == "TaskPay Earn"


def test_wallets_still_holding_funds_and_suspected_mules_are_in_the_ledger(engine_client):
    items = engine_client.get(f"/api/officer/cases/{traced(engine_client, IDLE)}/identifiers").json()
    holding = [i for i in by_kind(items, "wallet") if "holding funds" in (i["label"] or "").lower()]
    assert holding and all(i["confidence"] > 0 for i in holding)
    assert any(i["role"] == "mule_suspect" and i["label"].startswith("Suspected mule") for i in by_kind(items, "wallet"))


def test_the_ledger_has_no_duplicates_and_rebuilding_adds_nothing(engine_client):
    case = traced(engine_client, SWEEP)
    before = engine_client.get(f"/api/officer/cases/{case}/identifiers").json()
    assert len({(i["kind"], i["value"]) for i in before}) == len(before)
    assert ledger.build(case) == 0
    assert engine_client.get(f"/api/officer/cases/{case}/identifiers").json() == before
    assert len({i["identifier_id"] for i in before}) == len(before) and all(i["identifier_id"].startswith(f"I-{case}-") for i in before)


def test_seeded_cases_get_a_ledger_at_start_up(client):
    for case in client.get("/api/cases").json():
        items = client.get(f"/api/officer/cases/{case['case_id']}/identifiers").json()
        assert items and any(i["role"] == "reported" for i in items)
    c1 = by_kind(client.get("/api/officer/cases/C-001/identifiers").json(), "upi_id")
    assert c1 and c1[0]["value"] == "hero.invest@okaxis"
    assert ledger.ensure_all() == 0                                                        # nothing left to fill


def test_the_same_domain_written_two_ways_is_one_identifier(client):
    d2 = by_kind(client.get("/api/officer/cases/C-002/identifiers").json(), "domain")
    assert [i["value"] for i in d2] == ["hero-invest.example"]                         # "https://www.hero-invest.example/app"


def test_a_direct_trace_without_a_complaint_still_gets_a_ledger(client):
    case = client.post("/api/trace", json={"complaint_id": "NO-COMPLAINT", "wallet": GOOD["wallet"], "amount": 100}).json()["case_id"]
    items = client.get(f"/api/officer/cases/{case}/identifiers").json()
    assert [i["role"] for i in by_kind(items, "wallet")][0] == "reported"


# ---- the leads rules
def test_leads_come_from_the_ledger_and_cover_the_core_choke_points(engine_client):
    case = traced(engine_client, SWEEP)
    leads = engine_client.get(f"/api/officer/cases/{case}/leads").json()
    Lead(**leads[0])
    points = {l["choke_point"] for l in leads}
    assert {"exchange", "telecom", "messaging_platform", "domain_host", "payment_app"} <= points
    ex = next(l for l in leads if l["choke_point"] == "exchange")
    assert ex["holder"].startswith("Example Exchange B") and ex["requests"][:2] == ["kyc_request", "freeze_request"]
    assert "linked bank accounts" in ex["what_it_identifies"]


def test_leads_are_sorted_urgent_first(engine_client):
    leads = engine_client.get(f"/api/officer/cases/{traced(engine_client, IDLE)}/leads").json()
    order = {"urgent": 0, "high": 1, "normal": 2}
    assert [order[l["priority"]] for l in leads] == sorted(order[l["priority"]] for l in leads)
    assert leads[0]["priority"] == "urgent"


def test_a_bank_account_is_an_urgent_freeze_lead_to_that_bank(engine_client):
    leads = engine_client.get(f"/api/officer/cases/{traced(engine_client, IDLE)}/leads").json()
    bank = next(l for l in leads if l["choke_point"] == "bank")
    assert bank["holder"] == "HDFC Bank" and bank["priority"] == "urgent" and "freeze_request" in bank["requests"]


def test_idle_funds_give_a_token_issuer_hold_lead(engine_client):
    leads = engine_client.get(f"/api/officer/cases/{traced(engine_client, IDLE)}/leads").json()
    issuer = next(l for l in leads if l["choke_point"] == "issuer")
    assert issuer["priority"] == "urgent" and issuer["requests"][0] == "issuer_hold" and "5,900" in issuer["rationale"]
    assert "No identity" in issuer["what_it_identifies"]


def test_a_phone_leads_to_the_telecom_operator_and_the_messaging_apps(engine_client):
    leads = engine_client.get(f"/api/officer/cases/{traced(engine_client, SWEEP)}/leads").json()
    tele = next(l for l in leads if l["choke_point"] == "telecom")
    assert "subscriber_request" in tele["requests"] and "SIM subscriber" in tele["what_it_identifies"]
    assert any(l["choke_point"] == "messaging_platform" and l["requests"] == ["platform_data_request"] for l in leads)


def test_a_handle_leads_to_its_platform_with_a_preservation_notice_first(engine_client):
    leads = engine_client.get(f"/api/officer/cases/{traced(engine_client, SWEEP)}/leads").json()
    handle = next(l for l in leads if l["holder"] == "Telegram")
    assert handle["requests"][0] == "preservation_notice" and handle["priority"] == "high"


def test_a_domain_and_an_app_lead_to_hosts_and_stores(engine_client):
    sweep = engine_client.get(f"/api/officer/cases/{traced(engine_client, SWEEP)}/leads").json()
    assert next(l for l in sweep if l["choke_point"] == "domain_host")["requests"] == ["preservation_notice", "registrant_request", "takedown_request"]
    task = engine_client.get(f"/api/officer/cases/{traced(engine_client, IDLE)}/leads").json()
    assert next(l for l in task if l["choke_point"] == "app_store")["requests"][1] == "developer_request"


def test_a_upi_id_names_the_likely_app(engine_client):
    leads = engine_client.get(f"/api/officer/cases/{traced(engine_client, SWEEP)}/leads").json()
    upi = next(l for l in leads if l["choke_point"] == "payment_app")
    assert upi["holder"] == "Likely PhonePe (from the handle)"


def test_lead_ids_are_stable_and_unique(engine_client):
    case = traced(engine_client, SWEEP)
    a = engine_client.get(f"/api/officer/cases/{case}/leads").json()
    assert a == engine_client.get(f"/api/officer/cases/{case}/leads").json()
    assert len({l["lead_id"] for l in a}) == len(a)


def test_identifiers_with_no_rule_yet_give_no_lead(client):
    case = "C-001"
    for kind, value in (("email", "a@b.com"), ("ip_address", "10.1.1.1"), ("device", "imei-123")):
        assert client.post(f"/api/officer/cases/{case}/identifiers", json={"kind": kind, "value": value}).status_code == 201
    ids = {i["identifier_id"] for i in client.get(f"/api/officer/cases/{case}/identifiers").json() if i["kind"] in ("email", "ip_address", "device")}
    assert not ids & {l["identifier_id"] for l in client.get(f"/api/officer/cases/{case}/leads").json()}


# ---- the officer routes
def test_an_officer_can_add_an_identifier_by_hand(client):
    r = client.post("/api/officer/cases/C-004/identifiers", json={"kind": "phone", "value": "+91 98000 12345", "label": "Called the victim"})
    assert r.status_code == 201
    i = r.json()
    assert (i["value"], i["source"], i["role"], i["label"]) == ("9800012345", "officer", "other", "Called the victim")
    assert any(l["identifier_id"] == i["identifier_id"] and l["choke_point"] == "telecom" for l in client.get("/api/officer/cases/C-004/leads").json())


def test_adding_something_already_there_is_refused(client):
    body = {"kind": "domain", "value": "https://HERO-INVEST.example/x"}
    assert client.post("/api/officer/cases/C-001/identifiers", json=body).status_code == 409


def test_bad_identifiers_are_refused(client):
    assert client.post("/api/officer/cases/C-001/identifiers", json={"kind": "telepathy", "value": "x"}).status_code == 422
    assert client.post("/api/officer/cases/C-001/identifiers", json={"kind": "phone", "value": "   "}).status_code == 422
    assert client.post("/api/officer/cases/C-001/identifiers", json={"kind": "bank_account", "value": "abc"}).status_code == 422
    assert client.post("/api/officer/cases/C-001/identifiers", json={"kind": "phone", "value": "x" * 301}).status_code == 422


def test_unknown_cases_are_404(client):
    for path in ("identifiers", "leads"):
        assert client.get(f"/api/officer/cases/C-999/{path}").status_code == 404
    assert client.post("/api/officer/cases/C-999/identifiers", json={"kind": "phone", "value": "9876543210"}).status_code == 404


def test_the_ledger_survives_a_restart(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch, "fixture") as c:
        c.post("/api/officer/cases/C-001/identifiers", json={"kind": "email", "value": "x@y.com"})
    with make_client(tmp_path, monkeypatch, "fixture") as c:
        assert by_kind(c.get("/api/officer/cases/C-001/identifiers").json(), "email")[0]["value"] == "x@y.com"


def test_openapi_lists_the_investigation_routes():
    import main
    paths = main.app.openapi()["paths"]
    for p in ("/api/officer/cases/{case_id}/identifiers", "/api/officer/cases/{case_id}/leads"):
        assert p in paths


def test_the_two_sextortion_complaints_share_one_handle_across_cases(client):
    h4 = by_kind(client.get("/api/officer/cases/C-004/identifiers").json(), "social_handle")[0]["value"]
    h5 = by_kind(client.get("/api/officer/cases/C-005/identifiers").json(), "social_handle")[0]["value"]
    assert h4 == h5 == "private_pics_demo"                                                  # what stage 4.4 will link on
