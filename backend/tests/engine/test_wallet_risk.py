"""Step 6.7: GET /api/wallets/{address}/risk, from the engine seam and through the API."""
import base58
import hashlib

import pytest

import engine
from contract.schemas import WalletRisk
from engine.model.scoring import MAX_REASONS, TRUNCATED_REASON

HERO_SCAM = "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo"
MULE_1 = "TMhTyFX8dfbnrswVFDYwoM6bXz1LjZ3ZXt"
HOT_WALLET = "TJ4imTmNr3FZoqR2jsRBuXS2aNXNAsAXhK"          # Example Exchange A hot wallet
DEPOSIT_ADDR = "TK2HrF4zDufshHLhF2cCgENoBZipWxHvJK"        # published deposit address of Example Exchange B
BRIDGE = "TXzK7i61kT3ck6kZ3VeGZjUnPVwDS46sKM"
MIXER = "TLhZTYvV5asB99Wz26sSandSaN1kZfFWbs"
TRUNCATED_REAL = "TW8A5iWMfH7ArbeyW6UeizC8kw3wGPK49n"
REAL_FLAGGED = ["TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z", "TP6jUy5qZedW2KZpJfFEEAbGVyD9kQXn6k", "TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu"]
VALID_BUT_UNCACHED = base58.b58encode_check(b"\x41" + hashlib.sha256(b"never-cached").digest()[:20]).decode()


# ---- labeled addresses
@pytest.mark.parametrize("address,risk,score,reason", [
    (HOT_WALLET, "Low", 0.05, "Labeled exchange hot wallet"),
    (DEPOSIT_ADDR, "Low", 0.12, "Behaves like an exchange deposit address"),
    (BRIDGE, "Medium", 0.45, "Cross-chain bridge contract"),
    (MIXER, "Critical", 0.91, "Known mixing service"),
])
def test_labeled_addresses_get_fixed_values(address, risk, score, reason):
    r = engine.wallet_risk(address)
    assert (r.risk, r.risk_score, r.reasons, r.typology) == (risk, score, [reason], "unknown")


# ---- scored from their own transfers
def test_hero_pass_through_wallet_is_high_or_critical_with_reasons():
    r = engine.wallet_risk(MULE_1)
    assert r.risk in ("High", "Critical") and 0.5 <= r.risk_score <= 1.0
    assert 2 <= len(r.reasons) <= MAX_REASONS and r.address == MULE_1


def test_the_reported_hero_wallet_can_be_scored_here_and_gets_its_typology():
    r = engine.wallet_risk(HERO_SCAM)
    assert r.risk in ("High", "Critical") and r.typology == "investment_scam"


def test_low_risk_wallets_do_not_carry_a_typology():
    for a in REAL_FLAGGED:
        r = engine.wallet_risk(a)
        assert r.risk == "Low" and r.typology == "unknown" and r.reasons == ["No strong fraud signals"]


def test_a_partly_fetched_wallet_is_capped_and_says_so():
    r = engine.wallet_risk(TRUNCATED_REAL)
    assert r.risk == "Medium" and r.reasons[0] == TRUNCATED_REASON and len(r.reasons) <= MAX_REASONS


def test_standalone_score_agrees_with_the_trace_on_the_level_of_the_hero_wallets():
    from contract.schemas import TraceRequest
    t = engine.trace_complaint(TraceRequest(complaint_id="x", wallet=HERO_SCAM, amount=12000.0))
    for n in t.graph.nodes:
        if n.type == "intermediary" and n.hop == 1:
            assert engine.wallet_risk(n.id).risk == n.risk


# ---- addresses we cannot score
def test_valid_but_unknown_tron_address_is_low_with_the_no_history_reason():
    r = engine.wallet_risk(VALID_BUT_UNCACHED)
    assert (r.risk, r.risk_score, r.reasons) == ("Low", 0.0, ["No transaction history found"])


@pytest.mark.parametrize("address,fragment", [
    ("0xd90e2f925da726b50c4ed8d0fb90ad053324f31b", "Ethereum address and only TRON"),
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "Bitcoin address and only TRON"),
    ("So11111111111111111111111111111111111111112", "Solana address and only TRON"),
    ("TXyz", "not a valid wallet address"),
    ("", "not a valid wallet address"),
    ("not-an-address", "not a valid wallet address"),
])
def test_unscorable_addresses_are_low_with_a_reason_not_an_error(address, fragment):
    r = engine.wallet_risk(address)
    assert (r.risk, r.risk_score, r.typology) == ("Low", 0.0, "unknown") and fragment in r.reasons[0]


def test_every_answer_is_contract_valid_and_deterministic():
    for a in [HOT_WALLET, MULE_1, HERO_SCAM, TRUNCATED_REAL, VALID_BUT_UNCACHED, "TXyz", *REAL_FLAGGED]:
        r = engine.wallet_risk(a)
        WalletRisk(**r.model_dump())
        assert 0 <= r.risk_score <= 1 and r.reasons and r == engine.wallet_risk(a)


def test_tracing_fixture_switch_still_returns_the_fixture(monkeypatch):
    monkeypatch.setenv("TRACING", "fixture")
    r = engine.wallet_risk(MULE_1)
    assert r.address == MULE_1 and r.risk_score == 0.96            # the old hero fixture value


# ---- through the API
@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ENGINE_MODE", "engine")
    with TestClient(main.app) as c:
        yield c


def test_api_returns_the_real_score_in_engine_mode(client):
    body = client.get(f"/api/wallets/{MULE_1}/risk").json()
    assert body["address"] == MULE_1 and body["risk"] in ("High", "Critical") and len(body["reasons"]) >= 2
    assert client.get(f"/api/wallets/{MIXER}/risk").json()["risk"] == "Critical"


def test_api_handles_bad_addresses_without_an_error(client):
    r = client.get("/api/wallets/not-an-address/risk")
    assert r.status_code == 200 and r.json()["risk"] == "Low" and "not a valid" in r.json()["reasons"][0]


def test_api_in_fixture_mode_is_unchanged(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ENGINE_MODE", "fixture")
    with TestClient(main.app) as c:
        assert c.get(f"/api/wallets/{MULE_1}/risk").json()["risk_score"] == 0.82          # the seed trace's own node
        assert c.get(f"/api/wallets/{VALID_BUT_UNCACHED}/risk").json()["risk_score"] == 0.96  # else the hero fixture
