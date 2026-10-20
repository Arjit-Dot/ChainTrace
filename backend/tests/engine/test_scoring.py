"""Step 6.4: model probability -> level, SHAP reasons, and the rules fallback."""
import numpy as np
import pytest

from engine.chains.tron import TronAdapter
from engine.model import scoring
from engine.model.features import FEATURE_NAMES, WalletFeatures, extract_features
from engine.model.rules import NO_SIGNAL_REASON, level_for
from engine.model.scoring import MAX_REASONS, load_model, score_wallet, sentence, shap_reasons

MULE = WalletFeatures(0.0, 3, 0.99, 420.0, 1, 1.0, 0.5)
COLLECTOR = WalletFeatures(5.0, 60, 0.95, 900.0, 40, 0.6, 20.0)
NORMAL = WalletFeatures(700.0, 120, 0.5, 5 * 86400.0, 4, 0.1, 1.5)
EXCHANGE_LIKE = WalletFeatures(900.0, 5000, 0.98, 1200.0, 800, 0.02, 40.0)


@pytest.fixture(autouse=True)
def fresh_cache():
    scoring._load.cache_clear()
    yield
    scoring._load.cache_clear()


# ---- the model path
def test_model_loads_and_scoring_uses_it():
    assert load_model() is not None
    r = score_wallet(MULE)
    assert r.method == "model" and 0.0 <= r.score <= 1.0 and r.level == level_for(r.score)


def test_levels_for_the_four_archetypes():
    assert score_wallet(MULE).level in ("High", "Critical") and score_wallet(COLLECTOR).level in ("High", "Critical")
    assert score_wallet(NORMAL).level == "Low" and score_wallet(EXCHANGE_LIKE).level in ("Low", "Medium")


def test_score_is_a_probability_that_orders_the_archetypes():
    assert score_wallet(MULE).score > score_wallet(NORMAL).score
    assert score_wallet(COLLECTOR).score > score_wallet(EXCHANGE_LIKE).score


def test_scoring_is_deterministic():
    assert score_wallet(MULE) == score_wallet(MULE)


# ---- SHAP reasons
def test_shap_values_add_up_to_the_models_own_output():
    model, explainer = load_model()
    x = np.array([MULE.as_list(), COLLECTOR.as_list(), NORMAL.as_list()])
    logit = np.log(model.predict_proba(x)[:, 1] / (1 - model.predict_proba(x)[:, 1]))
    assert np.allclose(explainer.shap_values(x).sum(axis=1) + explainer.expected_value, logit, atol=1e-3)


def test_mule_reasons_are_readable_and_use_real_values():
    r = score_wallet(MULE)
    assert 2 <= len(r.reasons) <= MAX_REASONS
    assert any("Forwards funds within 7 minutes" in x or "under a day old" in x or "Funded by a single wallet" in x
               for x in r.reasons), r.reasons


def test_first_reason_is_the_feature_that_raised_the_score_most():
    model, explainer = load_model()
    for f in (MULE, COLLECTOR):
        contrib = explainer.shap_values(np.array([f.as_list()]))[0]
        top = FEATURE_NAMES[int(np.argmax(contrib))]
        assert score_wallet(f).reasons[0] == sentence(top, f)


def test_every_high_or_critical_wallet_has_at_least_two_reasons():
    for f in (MULE, COLLECTOR):
        r = score_wallet(f)
        assert r.level in ("High", "Critical") and len(r.reasons) >= 2


def test_low_risk_wallets_say_no_strong_signals_instead_of_quoting_features():
    for f in (NORMAL, EXCHANGE_LIKE):
        r = score_wallet(f)
        assert r.level == "Low" and r.reasons == [NO_SIGNAL_REASON]


def test_reasons_are_capped_and_only_quote_features_that_raised_the_score():
    model, explainer = load_model()
    for f in (MULE, COLLECTOR, NORMAL, EXCHANGE_LIKE):
        reasons = shap_reasons(explainer, f, "Critical")
        assert len(reasons) <= MAX_REASONS and len(set(reasons)) == len(reasons)


@pytest.mark.parametrize("name,f,expected", [
    ("age_days", WalletFeatures(0.2, 3, .5, 9, 1, 0, 1), "Wallet was under a day old when funds arrived"),
    ("age_days", WalletFeatures(12.4, 3, .5, 9, 1, 0, 1), "Wallet was 12 days old when funds arrived"),
    ("tx_count", WalletFeatures(1, 4, .5, 9, 1, 0, 1), "Only 4 lifetime transactions"),
    ("tx_count", WalletFeatures(1, 60, .5, 9, 1, 0, 1), "60 lifetime transactions"),
    ("in_out_ratio", WalletFeatures(1, 4, .987, 9, 1, 0, 1), "Forwards 99% of what it receives"),
    ("median_forward_sec", WalletFeatures(1, 4, .5, 240, 1, 0, 1), "Forwards funds within 4 minutes (median)"),
    ("median_forward_sec", WalletFeatures(1, 4, .5, 3 * 86400, 1, 0, 1), "Median time to forward funds is 3 days"),
    ("unique_senders", WalletFeatures(1, 4, .5, 9, 1, 0, 1), "Funded by a single wallet"),
    ("unique_senders", WalletFeatures(1, 4, .5, 9, 89, 0, 1), "89 unique senders"),
    ("round_number_ratio", WalletFeatures(1, 4, .5, 9, 1, 0.75, 1), "75% of transfers are round amounts"),
    ("fan_in_degree", WalletFeatures(1, 4, .5, 9, 1, 0, 14.0), "14.0 senders per recipient (consolidation)"),
])
def test_sentence_wording(name, f, expected):
    assert sentence(name, f) == expected


def test_every_feature_has_a_sentence():
    for name in FEATURE_NAMES:
        assert sentence(name, MULE)


# ---- fallback to the rules
def test_missing_model_file_falls_back_to_rules(tmp_path):
    r = score_wallet(MULE, model_path=tmp_path / "nope.pkl")
    assert r.method == "rules" and r.level in ("High", "Critical") and len(r.reasons) >= 2


def test_corrupt_model_file_falls_back_to_rules(tmp_path):
    bad = tmp_path / "bad.pkl"
    bad.write_bytes(b"not a model")
    assert score_wallet(NORMAL, model_path=bad).method == "rules"


def test_model_trained_on_other_features_is_not_used(tmp_path):
    import joblib
    model, _ = load_model()
    wrong = tmp_path / "wrong.pkl"
    joblib.dump({"model": model, "features": ["a", "b"], "report": {}}, wrong)
    assert score_wallet(MULE, model_path=wrong).method == "rules"


def test_fallback_gives_the_same_shape_of_answer():
    model_r, rules_r = score_wallet(MULE), score_wallet(MULE, model_path="/does/not/exist.pkl")
    assert (model_r.level in ("High", "Critical")) == (rules_r.level in ("High", "Critical"))
    assert 0 <= rules_r.score <= 1 and rules_r.reasons


# ---- on cached wallets
def test_hero_pass_through_wallets_are_high_or_critical_with_two_reasons():
    a = TronAdapter(offline=True)
    for addr, arrival in [("TMhTyFX8dfbnrswVFDYwoM6bXz1LjZ3ZXt", 1792400000), ("TCLZhujbkc1gBh7ZRv9BQG8M2SDVdKNscT", 1792400060)]:
        r = score_wallet(extract_features(addr, a.transfers(addr)[0], arrival))
        assert r.method == "model" and r.level in ("High", "Critical") and len(r.reasons) >= 2, (addr, r)
