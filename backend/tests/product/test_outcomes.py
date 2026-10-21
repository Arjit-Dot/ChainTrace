"""Investigation 4.2: where the money went (per kind of endpoint) and the suspected mules."""
import json

import pytest
from fastapi.testclient import TestClient

from contract.schemas import Mule, Outcome
from paths import SCENARIOS, SCENARIOS_JSON
from product import complaints, outcomes

SCEN = {s["key"]: s for s in json.loads(SCENARIOS_JSON.read_text())}
REAL = json.loads((SCENARIOS / "real_case.json").read_text())
HERO = "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo"
SWEEP, IDLE = "NCRP-2026-104317", "NCRP-2026-258846"


@pytest.fixture
def client(tmp_path, monkeypatch):
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ENGINE_MODE", "engine")
    monkeypatch.setenv("CHAINTRACE_MONITOR", "0")
    complaints._tracing.clear()
    with TestClient(main.app) as c:
        yield c


def trace_wallet(c, wallet, amount, **over):
    body = {"wallet": wallet, "amount": amount, "reporter_name": "T", "reporter_mobile": "9811122233", **over}
    cid = c.post("/api/complaints", json=body).json()["complaint_id"]
    return c.post(f"/api/officer/complaints/{cid}/trace").json()["case_id"]


def trace_seeded(c, cid):
    return c.post(f"/api/officer/complaints/{cid}/trace").json()["case_id"]


def outs(c, case):
    r = c.get(f"/api/officer/cases/{case}/outcomes")
    assert r.status_code == 200
    return [Outcome(**o) for o in r.json()]


def kinds(os):
    return [o.kind for o in os]


# ---- an exchange (VASP)
def test_an_exchange_outcome_asks_for_kyc_and_a_freeze(client):
    case = trace_seeded(client, SWEEP)
    os = outs(client, case)
    assert kinds(os) == ["vasp"]                                           # the hot wallet behind the deposit address is not a second outcome
    o = os[0]
    assert o.title == "Funds reached Example Exchange B" and o.status == "action_needed" and o.amount == 4950.0
    assert o.handling[0].startswith("Send the KYC and freeze request to Example Exchange B")
    assert any("bank accounts" in h and "mule accounts" in h for h in o.handling)
    leads = {l["lead_id"] for l in client.get(f"/api/officer/cases/{case}/leads").json() if l["choke_point"] == "exchange"}
    assert set(o.lead_ids) == leads and leads


def test_the_exchange_outcome_moves_to_in_progress_once_the_notice_is_sent(client):
    case = trace_seeded(client, SWEEP)
    notice = client.get(f"/api/cases/{case}/freeze-notice").json()
    client.post("/api/integrations/sahyog/notice", json={k: notice[k] for k in ("case_id", "to_vasp", "subject", "body")})
    (o,) = outs(client, case)
    assert o.status == "in_progress" and "(sent)" in o.handling[0]


def test_the_real_binance_flow_has_one_exchange_outcome(client):
    case = trace_wallet(client, REAL["wallet"], REAL["amount"])
    os = outs(client, case)
    assert kinds(os) == ["vasp"] and "Binance" in os[0].title


# ---- a DEX
def test_a_dex_pool_is_a_terminal_node_with_no_account_holder(client):
    case = trace_wallet(client, SCEN["dex"]["wallet"], 4000)
    t = client.get(f"/api/cases/{case}").json()
    dex = next(n for n in t["graph"]["nodes"] if n["type"] == "dex")
    assert dex["label"].startswith("SunSwap") and dex["risk"] == "Medium" and "no account holder" in dex["reasons"][0]
    assert not any(e["source"] == dex["id"] for e in t["graph"]["edges"])                    # the trace stops at the pool
    assert any(e["target"] == dex["id"] and e["edge_type"] == "swap" for e in t["graph"]["edges"])
    assert t["nearest_vasp"] is None                                                         # a DEX is not a VASP


def test_a_dex_outcome_says_what_cannot_be_done_and_what_can(client):
    case = trace_wallet(client, SCEN["dex"]["wallet"], 4000)
    (o,) = [x for x in outs(client, case) if x.kind == "dex"]
    assert o.status == "info" and o.amount == 3950.0 and "SunSwap" in o.title
    text = " ".join(o.handling)
    assert "no account holder" in text and "cannot be asked for KYC or told to freeze" in text
    assert "follow the wallet that received the swapped tokens" in text and "token issuer" in text and "Preserve" in text
    assert o.lead_ids == []                                                                  # nothing to ask a pool


def test_a_dex_gets_a_follow_the_swap_recommendation(client):
    case = trace_wallet(client, SCEN["dex"]["wallet"], 4000)
    recs = {r["action"]: r for r in client.get(f"/api/cases/{case}").json()["recommendations"]}
    assert "Follow the swap" in recs and recs["Follow the swap"]["priority"] == "high" and "3,950 USDT" in recs["Follow the swap"]["detail"]
    assert "Issue freeze and KYC request" not in " ".join(recs)


# ---- a bank account
def test_a_bank_account_the_victim_paid_needs_a_freeze_to_that_bank(client):
    case = trace_seeded(client, IDLE)
    o = next(x for x in outs(client, case) if x.kind == "bank_account")
    assert o.status == "action_needed" and o.subject == "000123450001" and o.subject_label == "HDFC Bank" and "at HDFC Bank" in o.title
    assert o.handling[0] == "Send a freeze or lien request to HDFC Bank"
    assert any("CCTV" in h for h in o.handling) and any("another mule" in h for h in o.handling)
    leads = {l["lead_id"]: l for l in client.get(f"/api/officer/cases/{case}/leads").json()}
    assert [leads[i]["choke_point"] for i in o.lead_ids] == ["bank"]


def test_a_bank_account_with_an_unknown_bank_asks_for_the_ifsc_to_find_it(client):
    case = trace_wallet(client, SCEN["idle"]["wallet"], 6000, paid_to_bank_account="999888777", paid_to_ifsc="ZZZZ0000001")
    o = next(x for x in outs(client, case) if x.kind == "bank_account")
    assert o.handling[0] == "Send a freeze or lien request to the bank (identify it from the IFSC code)"


# ---- idle funds, mixers, bridges
def test_funds_still_sitting_in_a_wallet_need_an_issuer_hold_now(client):
    case = trace_seeded(client, IDLE)
    os = outs(client, case)
    o = next(x for x in os if x.kind == "idle_wallet")
    assert o.amount == 5900.0 and o.status == "action_needed" and "hold the 5,900 USDT now" in o.handling[0] and len(o.lead_ids) == 1
    assert [x.status for x in os] == sorted((x.status for x in os), key=lambda s: outcomes.STATUS_ORDER[s])     # urgent first


def test_the_reported_wallet_still_holding_the_money_is_an_idle_outcome(client, monkeypatch):
    import base58
    import hashlib
    import engine
    from tests.support import FakeAdapter, T0, tx
    root = base58.b58encode_check(b"\x41" + hashlib.sha256(b"only-receives").digest()[:20]).decode()
    monkeypatch.setattr(engine, "_adapter", lambda: FakeAdapter([tx("V", root, 1000, T0)]))
    case = client.post("/api/trace", json={"complaint_id": "H", "wallet": root, "amount": 1000}).json()["case_id"]
    (o,) = outs(client, case)
    assert (o.kind, o.amount, o.subject, o.status) == ("idle_wallet", 1000.0, root, "action_needed")


def test_a_mixer_cannot_be_followed(client):
    case = trace_wallet(client, SCEN["mixer"]["wallet"], 4000)
    (o,) = [x for x in outs(client, case) if x.kind == "mixer"]
    assert o.status == "info" and "cannot be followed through a mixer" in o.handling[0] and "Example Mixer" in o.title


def test_a_bridge_without_a_seeded_exit_needs_following_on_the_other_chain(client):
    case = trace_wallet(client, SCEN["bridge"]["wallet"], 4000)
    (o,) = [x for x in outs(client, case) if x.kind == "bridge"]
    assert o.status == "action_needed" and o.handling[0] == "Continue the trace on the destination chain"


def test_the_hero_case_shows_an_exchange_a_continued_bridge_and_idle_funds_on_the_other_chain(client):
    case = trace_wallet(client, HERO, 12000)
    os = outs(client, case)
    assert set(kinds(os)) == {"vasp", "bridge", "idle_wallet"}
    bridge = next(o for o in os if o.kind == "bridge")
    assert bridge.status == "in_progress" and "Ethereum" in bridge.handling[0]
    assert next(o for o in os if o.kind == "idle_wallet").amount == 3720.0
    assert os[0].status == "action_needed"


def test_a_trace_that_reaches_nothing_says_so(client):
    case = client.post("/api/trace", json={"complaint_id": "Z", "wallet": "TXyz", "amount": 1}).json()["case_id"]
    (o,) = outs(client, case)
    assert o.kind == "dead_end" and o.status == "info" and "ended without reaching" in o.title


# ---- the mules
def test_suspected_mule_wallets_show_what_they_received_forwarded_and_where_it_went(client):
    case = trace_seeded(client, SWEEP)
    ms = [Mule(**m) for m in client.get(f"/api/officer/cases/{case}/mules").json()]
    (m,) = [x for x in ms if x.kind == "wallet"]
    assert m.risk in ("High", "Critical") and m.received == 5000.0 and m.forwarded == 4950.0 and m.onward == ["vasp"] and m.hop == 1
    assert 2 <= len(m.reasons) <= 3 and m.identifier_id and m.identifier_id.startswith(f"I-{case}-")


def test_a_bank_account_is_a_suspected_mule_account_with_a_caution(client):
    case = trace_seeded(client, IDLE)
    ms = [Mule(**m) for m in client.get(f"/api/officer/cases/{case}/mules").json()]
    bank = next(x for x in ms if x.kind == "bank_account")
    assert bank.value == "000123450001" and bank.label == "HDFC Bank" and bank.risk is None
    assert any("may be a victim too" in r for r in bank.reasons)


def test_mules_are_biggest_first_and_always_only_suspected(client):
    case = trace_wallet(client, REAL["wallet"], REAL["amount"])
    ms = [Mule(**m) for m in client.get(f"/api/officer/cases/{case}/mules").json()]
    assert [m.received for m in ms] == sorted((m.received for m in ms), reverse=True)
    body = json.dumps(client.get(f"/api/officer/cases/{case}/mules").json()).lower()
    assert "confirmed" not in body and "guilty" not in body


def test_only_wallets_the_model_rates_high_or_critical_are_listed(client):
    case = trace_wallet(client, REAL["wallet"], REAL["amount"])
    t = client.get(f"/api/cases/{case}").json()
    flagged = {n["id"] for n in t["graph"]["nodes"] if n["hop"] >= 1 and n["type"] in ("intermediary", "unknown") and n["risk"] in ("High", "Critical")}
    assert {m["value"] for m in client.get(f"/api/officer/cases/{case}/mules").json() if m["kind"] == "wallet"} == flagged


# ---- every case, and the routes
def test_every_seeded_case_has_outcomes_and_mules_without_error(client):
    for c in client.get("/api/cases").json():
        assert outs(client, c["case_id"])
        assert client.get(f"/api/officer/cases/{c['case_id']}/mules").status_code == 200


def test_outcome_ids_are_stable_and_unique(client):
    case = trace_seeded(client, IDLE)
    a = client.get(f"/api/officer/cases/{case}/outcomes").json()
    assert a == client.get(f"/api/officer/cases/{case}/outcomes").json()
    assert len({o["outcome_id"] for o in a}) == len(a)


def test_unknown_cases_are_404(client):
    for path in ("outcomes", "mules"):
        assert client.get(f"/api/officer/cases/C-999/{path}").status_code == 404


def test_openapi_lists_the_new_routes():
    import main
    paths = main.app.openapi()["paths"]
    assert "/api/officer/cases/{case_id}/outcomes" in paths and "/api/officer/cases/{case_id}/mules" in paths
