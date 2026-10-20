"""
Step 6.3b: does the scorer hold up on wallets it was not built from? Scenario battery (DEV set), edge cases,
robustness to small changes, and properties that must hold for any wallet.

These are our own simulated scenarios with our own labels, so they test robustness against our assumptions,
not accuracy on real fraud. (The HOLDOUT battery lives in test_holdout.py.)
"""
import numpy as np
import pytest

from engine.model.battery import DEV, instances, run_battery, summarize
from engine.model.features import WalletFeatures, extract_features
from engine.model.rules import rule_score
from engine.model.scoring import NO_HISTORY_REASON, THIN_CAP, THIN_REASON, load_model, score_wallet, thin_history
from tests.support import T0, tx

W = "W"


def model_score(f):
    return score_wallet(f).score


# ---- the DEV battery
@pytest.fixture(scope="module")
def model_report():
    return run_battery(model_score, DEV, n=40, seed=0)


@pytest.fixture(scope="module")
def rules_report():
    return run_battery(rule_score, DEV, n=40, seed=0)


def test_battery_is_diverse():
    kinds = {s.kind for s in DEV}
    assert kinds == {"firm_fraud", "hard_fraud", "firm_benign", "ambiguous"} and len(DEV) >= 18
    assert len({s.name for s in DEV}) == len(DEV)


def test_scenarios_produce_valid_feature_vectors():
    for sc in DEV:
        for f in instances(sc, 5, 1):
            assert f.tx_count >= 1 and 0 <= f.in_out_ratio <= 1 and f.age_days >= 0, sc.name


def test_model_on_the_dev_battery(model_report):
    s = summarize(model_report)
    assert s["mean_pass_rate"] >= 0.95 and s["worst_rate"] >= 0.80, (s, {k: v["pass_rate"] for k, v in model_report.items()})


def test_rules_on_the_dev_battery(rules_report):
    s = summarize(rules_report)
    assert s["mean_pass_rate"] >= 0.95 and s["worst_rate"] >= 0.85, (s, {k: v["pass_rate"] for k, v in rules_report.items()})


def test_every_firm_fraud_scenario_is_caught_by_both(model_report, rules_report):
    for rep in (model_report, rules_report):
        for name, row in rep.items():
            if row["kind"] == "firm_fraud":
                assert row["pass_rate"] >= 0.95, (name, row)


def test_ambiguous_scenarios_are_reported_not_judged(model_report):
    amb = {k: v for k, v in model_report.items() if v["kind"] == "ambiguous"}
    assert amb and all(v["pass_rate"] is None for v in amb.values())


# ---- feature extraction properties
def test_amounts_scale_does_not_change_the_features():
    ts = [tx("A", W, 1000, T0), tx("B", W, 500, T0 + 100), tx(W, "C", 1400, T0 + 400)]
    big = [tx(t.from_addr, t.to_addr, t.amount * 1000, t.timestamp) for t in ts]
    a, b = extract_features(W, ts), extract_features(W, big)
    assert (a.in_out_ratio, a.median_forward_sec, a.unique_senders) == (b.in_out_ratio, b.median_forward_sec, b.unique_senders)


def test_old_dust_does_not_hide_a_fast_big_forward():
    ts = [tx("D", W, 3, T0 - 60 * 86400), tx("A", W, 20000, T0), tx(W, "B", 19900, T0 + 180)]
    assert extract_features(W, ts, arrival_ts=T0).median_forward_sec == 180.0


# ---- edge cases through the whole path (transfers -> features -> score)
EDGE = {
    "single_incoming": [tx("A", W, 100, T0)],
    "single_outgoing": [tx(W, "B", 100, T0)],
    "same_timestamp_in_out": [tx("A", W, 100, T0), tx(W, "B", 100, T0)],
    "zero_amounts": [tx("A", W, 0, T0), tx(W, "B", 0, T0 + 5)],
    "huge_amounts": [tx("A", W, 1e15, T0), tx(W, "B", 1e15, T0 + 60)],
    "tiny_amounts": [tx("A", W, 1e-9, T0), tx(W, "B", 1e-9, T0 + 60)],
    "self_transfer": [tx(W, W, 100, T0)],
    "duplicates": [tx("A", W, 100, T0), tx("A", W, 100, T0)],
    "outgoing_before_incoming": [tx(W, "B", 100, T0), tx("A", W, 100, T0 + 100)],
    "only_incoming_many": [tx(f"S{i}", W, 50, T0 + i) for i in range(30)],
}


@pytest.mark.parametrize("name", sorted(EDGE))
def test_edge_case_gives_a_valid_answer(name):
    f = extract_features(W, EDGE[name])
    assert all(np.isfinite(f.as_list()))
    for r in (score_wallet(f), score_wallet(f, model_path="/missing.pkl")):
        assert 0.0 <= r.score <= 1.0 and r.level in ("Low", "Medium", "High", "Critical") and r.reasons


def test_no_history_is_low_with_its_own_reason():
    r = score_wallet(extract_features(W, []))
    assert (r.level, r.score, r.reasons, r.method) == ("Low", 0.0, [NO_HISTORY_REASON], "none")


@pytest.mark.parametrize("name", ["single_incoming", "single_outgoing", "duplicates"])
def test_thin_history_is_capped_and_says_so(name):
    f = extract_features(W, EDGE[name])
    assert thin_history(f)
    r = score_wallet(f)
    assert r.score <= THIN_CAP and r.level in ("Low", "Medium") and r.reasons == [THIN_REASON]


def test_a_real_pass_through_is_not_mistaken_for_thin_history():
    f = extract_features(W, [tx("A", W, 8000, T0), tx(W, "B", 7850, T0 + 420)])
    assert not thin_history(f) and score_wallet(f).level in ("High", "Critical")


def test_extreme_feature_values_do_not_break_scoring():
    for f in (WalletFeatures(1e6, 10 ** 8, 1.0, 1.0, 10 ** 7, 1.0, 1e7), WalletFeatures(0, 1, 0, 1e9, 1, 0, 1e-4)):
        r = score_wallet(f)
        assert 0 <= r.score <= 1 and r.reasons


# ---- robustness
def test_small_changes_rarely_change_the_level():
    changed = total = 0
    for sc in DEV:
        for f in instances(sc, 15, 3):
            base = score_wallet(f)
            for key in ("age_days", "median_forward_sec", "fan_in_degree"):
                d = f.as_dict()
                d[key] *= 1.05
                changed += score_wallet(WalletFeatures(**d)).level != base.level
                total += 1
    assert changed / total < 0.03, (changed, total)


def test_round_amounts_alone_never_decide_the_level():
    mule = WalletFeatures(0.5, 3, 0.99, 420.0, 1, 0.0, 0.5)
    normal = WalletFeatures(700.0, 120, 0.5, 5 * 86400.0, 4, 0.0, 1.5)
    for round_share in (0.0, 0.5, 1.0):
        assert score_wallet(WalletFeatures(**{**mule.as_dict(), "round_number_ratio": round_share})).score >= 0.5
        assert score_wallet(WalletFeatures(**{**normal.as_dict(), "round_number_ratio": round_share})).score < 0.5


def test_model_score_never_falls_as_a_wallet_forwards_faster_or_is_younger_or_forwards_more():
    rng = np.random.default_rng(0)
    for _ in range(150):
        base = dict(age_days=float(np.exp(rng.uniform(-2, 7))), tx_count=int(np.exp(rng.uniform(1, 7))),
                    in_out_ratio=float(rng.uniform(0.1, 0.9)), median_forward_sec=float(np.exp(rng.uniform(3, 12))),
                    unique_senders=int(np.exp(rng.uniform(0, 5))), round_number_ratio=float(rng.uniform(0, 1)),
                    fan_in_degree=float(np.exp(rng.uniform(-2, 4))))
        s0 = score_wallet(WalletFeatures(**base)).score
        assert score_wallet(WalletFeatures(**{**base, "median_forward_sec": base["median_forward_sec"] / 3})).score >= s0 - 1e-6
        assert score_wallet(WalletFeatures(**{**base, "age_days": base["age_days"] / 3})).score >= s0 - 1e-6
        assert score_wallet(WalletFeatures(**{**base, "in_out_ratio": min(1.0, base["in_out_ratio"] + 0.1)})).score >= s0 - 1e-6


def test_clearly_fraud_and_clearly_benign_regions():
    """Sample inside regions where every sensible reading agrees, and require the right call every time."""
    rng = np.random.default_rng(1)
    for _ in range(300):
        fraud = WalletFeatures(float(rng.uniform(0, 5)), int(rng.integers(2, 21)), float(rng.uniform(0.9, 1.0)),
                               float(rng.uniform(30, 1200)), int(rng.integers(1, 5)), float(rng.uniform(0, 1)), float(rng.uniform(0.2, 3)))
        benign = WalletFeatures(float(rng.uniform(365, 2000)), int(rng.integers(4, 400)), float(rng.uniform(0.0, 0.6)),
                                float(rng.uniform(3 * 86400, 30 * 86400)), int(rng.integers(1, 12)), float(rng.uniform(0, 1)), float(rng.uniform(0.3, 3)))
        assert score_wallet(fraud).score >= 0.5, fraud
        assert score_wallet(benign).score < 0.5, benign
        assert rule_score(fraud) >= 0.5 and rule_score(benign) < 0.5


def test_scoring_is_deterministic_and_does_not_depend_on_input_order():
    ts = [tx("A", W, 100, T0), tx("B", W, 50, T0 + 90), tx(W, "C", 140, T0 + 400)]
    assert score_wallet(extract_features(W, ts)) == score_wallet(extract_features(W, list(reversed(ts))))
    assert load_model() is not None
