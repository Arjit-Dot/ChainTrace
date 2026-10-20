"""Step 6.3: synthetic data, the train/test split, the trained model and its saved file."""
import joblib
import numpy as np
import pytest

from engine.model.features import FEATURE_NAMES, WalletFeatures
from engine.model.rules import rule_score
from sklearn.metrics import roc_auc_score

from engine.model.synthetic import PROFILES, REAL_FLAGGED, make_synthetic, seed_rows
from engine.model.train import TEST_SHARE, evaluate, split, train
from paths import MODEL_PKL

HERO_MULES = ["TMhTyFX8dfbnrswVFDYwoM6bXz1LjZ3ZXt", "TCLZhujbkc1gBh7ZRv9BQG8M2SDVdKNscT"]


# ---- synthetic data
def test_shape_columns_and_class_balance():
    df = make_synthetic(2000, seed=1)
    assert len(df) == 2000 and set(FEATURE_NAMES) <= set(df.columns)
    shares = df["profile"].value_counts(normalize=True)
    for profile, (_, share) in PROFILES.items():
        assert shares[profile] == pytest.approx(share, abs=0.005), profile
    assert 0.35 < df["label"].mean() < 0.45


def test_same_seed_same_data_different_seed_different_data():
    a, b, c = make_synthetic(500, 7), make_synthetic(500, 7), make_synthetic(500, 8)
    assert a.equals(b) and not a.equals(c)


def test_values_are_in_valid_ranges():
    df = make_synthetic(3000, 3)
    assert (df["age_days"] >= 0).all() and (df["tx_count"] >= 1).all() and (df["unique_senders"] >= 1).all()
    assert df["in_out_ratio"].between(0, 1).all() and df["round_number_ratio"].between(0, 1).all()
    assert (df["median_forward_sec"] > 0).all() and (df["fan_in_degree"] > 0).all()


def test_no_single_feature_separates_the_classes():
    """The first model keyed on round amounts and age because the synthetic classes differed there. No feature may be a shortcut."""
    df = make_synthetic(6000, 42)
    for name in FEATURE_NAMES:
        auc = roc_auc_score(df["label"], df[name])
        assert max(auc, 1 - auc) < 0.90, (name, auc)
    auc = roc_auc_score(df["label"], df["round_number_ratio"])
    assert max(auc, 1 - auc) < 0.65


def test_classes_overlap_so_the_task_is_not_trivial():
    df = make_synthetic(6000, 42)
    assert 0.01 < df["flipped"].mean() < 0.06                                # noisy labels
    for col, cut in (("median_forward_sec", 900), ("age_days", 5)):          # fast forwarding and young wallets occur in both classes
        assert df[df[col] < cut]["label"].nunique() == 2, col


def test_profile_labels_follow_the_design():
    assert {p: l for p, (l, _) in PROFILES.items()} == {
        "fast_mule": 1, "slow_mule": 1, "collector": 1, "splitter": 1, "normal_user": 0, "new_user": 0,
        "exchange_hub": 0, "defi_bot": 0, "otc_trader": 0, "saver": 0, "charity_merchant": 0}
    df = make_synthetic(4000, 5)
    clean = df[~df["flipped"]]
    for profile, (label, _) in PROFILES.items():
        assert (clean[clean["profile"] == profile]["label"] == label).all()


# ---- seed rows and leakage
def test_seed_rows_come_from_the_scripted_cases_and_never_the_real_wallets():
    s = seed_rows()
    assert 10 <= len(s) <= 40 and set(s["label"]) == {0, 1}
    assert s["source"].str.startswith("seed:").all()
    assert "seed:hero" in set(s["source"])


def test_real_flagged_wallets_are_held_out_by_design():
    assert REAL_FLAGGED == {"TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z", "TP6jUy5qZedW2KZpJfFEEAbGVyD9kQXn6k",
                            "TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu"}


def test_split_is_stratified_and_seeds_only_in_train():
    train_df, test_df = split(2000, seed=11)
    assert len(test_df) == round(2000 * TEST_SHARE)
    assert (test_df["source"] == "synthetic").all()                          # nothing but synthetic in the test side
    assert train_df["source"].str.startswith("seed").sum() == len(seed_rows())
    shares = test_df["profile"].value_counts(normalize=True)
    for profile, (_, share) in PROFILES.items():
        assert shares[profile] == pytest.approx(share, abs=0.02), profile
    # no row appears on both sides
    key = lambda d: set(map(tuple, d[FEATURE_NAMES].round(6).to_numpy().tolist()))   # noqa: E731
    assert not (key(train_df[train_df["source"] == "synthetic"]) & key(test_df))


# ---- training
@pytest.fixture(scope="module")
def trained():
    return train(2000, seed=42)


def test_report_has_the_numbers_we_quote(trained):
    _, r = trained
    assert r["rows"]["test_synthetic"] == 500 and r["rows"]["train_seed"] == len(seed_rows())
    for side in ("model", "rules_baseline"):
        assert {"auc", "accuracy", "precision", "recall", "confusion", "by_profile_accuracy"} <= set(r[side])
    assert r["features"] == FEATURE_NAMES and "synthetic" in r["data_note"].lower()


def test_model_learns_the_task_but_is_not_perfect(trained):
    _, r = trained
    assert 0.90 < r["model"]["auc"] < 1.0, r["model"]            # good, but the overlap and noise keep it below 100%
    assert r["dev_battery"]["model"]["mean_pass_rate"] > 0.90
    assert r["model"]["confusion"]["fp"] + r["model"]["confusion"]["fn"] > 0


def test_training_is_repeatable(trained):
    model, _ = trained
    again, _ = train(2000, seed=42)
    x = make_synthetic(200, 99)[FEATURE_NAMES].to_numpy()
    assert np.allclose(model.predict_proba(x), again.predict_proba(x))


def test_model_does_not_lean_on_one_feature(trained):
    model, _ = trained
    assert max(model.feature_importances_) < 0.5, dict(zip(FEATURE_NAMES, model.feature_importances_))


def test_model_ranks_a_mule_above_a_normal_user(trained):
    model, _ = trained
    mule = WalletFeatures(0.0, 3, 0.99, 420.0, 1, 1.0, 0.5).as_list()
    normal = WalletFeatures(700.0, 120, 0.5, 5 * 86400.0, 4, 0.1, 1.5).as_list()
    p = model.predict_proba(np.array([mule, normal]))[:, 1]
    assert p[0] > 0.8 > 0.2 > p[1]


def test_evaluate_on_a_known_answer():
    import pandas as pd
    test = pd.DataFrame({"label": [1, 1, 0, 0], "profile": ["a", "a", "b", "b"]})
    m = evaluate(np.array([0.9, 0.4, 0.1, 0.6]), test)
    assert m["confusion"] == {"tn": 1, "fp": 1, "fn": 1, "tp": 1} and m["accuracy"] == 0.5
    assert m["by_profile_accuracy"] == {"a": 0.5, "b": 0.5}


# ---- the saved model file
def test_saved_model_loads_and_matches_the_feature_order():
    assert MODEL_PKL.exists(), "run: python data/scripts/train_risk_model.py"
    bundle = joblib.load(MODEL_PKL)
    assert bundle["features"] == FEATURE_NAMES and bundle["report"]["seed"] == 42
    p = bundle["model"].predict_proba(np.array([WalletFeatures(0.0, 3, 0.99, 420.0, 1, 1.0, 0.5).as_list()]))[:, 1]
    assert 0.0 <= p[0] <= 1.0 and p[0] > 0.5
    assert bundle["report"]["model"]["auc"] > bundle["report"]["rules_baseline"]["auc"]   # the model beats the rules here


def test_rules_on_the_same_features_are_available_as_a_baseline():
    assert 0.0 <= rule_score(WalletFeatures(0.0, 3, 0.99, 420.0, 1, 1.0, 0.5)) <= 1.0
