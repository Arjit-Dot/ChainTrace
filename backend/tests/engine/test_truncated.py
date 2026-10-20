"""A wallet whose history was only partly fetched must not be scored on its age or transfer count."""
import pytest

from engine.chains.tron import TronAdapter
from engine.model.features import WalletFeatures, extract_features
from engine.model.rules import NO_SIGNAL_REASON
from engine.model.scoring import THIN_CAP, TRUNCATED_CAP, TRUNCATED_REASON, score_wallet

# looks young, busy, fast and many-sender: what a truncated exchange hub looks like when only its newest 200 transfers are seen
HUB_SEEN_PARTLY = WalletFeatures(age_days=18.0, tx_count=200, in_out_ratio=1.0, median_forward_sec=1080.0,
                                 unique_senders=54, round_number_ratio=0.46, fan_in_degree=27.0)
MULE = WalletFeatures(0.0, 3, 0.99, 420.0, 1, 1.0, 0.5)


def test_without_the_flag_the_partly_seen_hub_scores_high():
    assert score_wallet(HUB_SEEN_PARTLY).level in ("High", "Critical")      # the false alarm we are guarding against


@pytest.mark.parametrize("model_path", [None, "/missing.pkl"])        # model path and rules fallback
def test_truncated_history_is_capped_at_medium(model_path):
    r = score_wallet(HUB_SEEN_PARTLY, model_path=model_path, truncated=True)
    assert r.score <= TRUNCATED_CAP == THIN_CAP and r.level in ("Low", "Medium")


@pytest.mark.parametrize("model_path", [None, "/missing.pkl"])
def test_truncated_reason_comes_first_and_age_and_count_are_never_quoted(model_path):
    r = score_wallet(HUB_SEEN_PARTLY, model_path=model_path, truncated=True)
    assert r.reasons[0] == TRUNCATED_REASON
    assert not any("old when funds arrived" in x or "lifetime transactions" in x or "under a day old" in x for x in r.reasons)


def test_other_signals_are_still_quoted():
    assert len(score_wallet(HUB_SEEN_PARTLY, truncated=True).reasons) >= 2          # the flag plus speed/senders


def test_a_complete_history_is_unchanged_by_the_flag_being_false():
    assert score_wallet(MULE, truncated=False) == score_wallet(MULE)
    assert score_wallet(MULE).level in ("High", "Critical")


def test_truncated_low_risk_wallet_does_not_say_no_signals_next_to_the_warning():
    normal = WalletFeatures(700.0, 200, 0.5, 5 * 86400.0, 4, 0.1, 1.5)
    r = score_wallet(normal, truncated=True)
    assert r.reasons == [TRUNCATED_REASON] and NO_SIGNAL_REASON not in r.reasons


def test_thin_history_takes_precedence_over_truncation():
    f = WalletFeatures(0.0, 1, 0.0, 604800.0, 1, 1.0, 1.0)
    assert score_wallet(f, truncated=True).reasons[0].startswith("Too little")


# ---- the real cached wallets that hit the 200-transfer limit
def test_the_real_wallet_that_looked_young_is_no_longer_critical():
    a = TronAdapter(offline=True)
    addr = "TW8A5iWMfH7ArbeyW6UeizC8kw3wGPK49n"
    f = extract_features(addr, a.transfers(addr)[0])
    assert f.tx_count == 200 and a.history_truncated(addr)
    assert score_wallet(f).level == "Critical"                                  # without the flag: the false alarm
    r = score_wallet(f, truncated=a.history_truncated(addr))
    assert r.level in ("Low", "Medium") and r.reasons[0] == TRUNCATED_REASON


def test_complete_real_wallets_are_scored_as_before():
    a = TronAdapter(offline=True)
    for addr in ("TLL6qxRKZjJWqLqUraqNebSe8k6AtZhr1P", "TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu"):
        assert a.cache_path(addr).exists() and not a.history_truncated(addr)
        f = extract_features(addr, a.transfers(addr)[0])
        assert score_wallet(f, truncated=a.history_truncated(addr)) == score_wallet(f)
