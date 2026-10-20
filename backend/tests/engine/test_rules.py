"""Step 6.2: the rule-based score, the level mapping and the reason sentences."""
import pytest

from engine.chains.tron import TronAdapter
from engine.model import rules
from engine.model.features import NEVER_FORWARDED_SEC, WalletFeatures, extract_features
from engine.model.rules import level_for, ramp, rule_reasons, rule_score, score_with_rules, signals


def wf(**kw):
    base = dict(age_days=400.0, tx_count=300, in_out_ratio=0.3, median_forward_sec=float(NEVER_FORWARDED_SEC),
                unique_senders=1, round_number_ratio=0.0, fan_in_degree=1.0)
    base.update(kw)
    return WalletFeatures(**base)


MULE = wf(age_days=0.0, tx_count=3, in_out_ratio=0.99, median_forward_sec=420.0, unique_senders=1,
          round_number_ratio=1.0, fan_in_degree=0.5)
COLLECTOR = wf(age_days=5.0, tx_count=60, in_out_ratio=0.95, median_forward_sec=900.0, unique_senders=40,
               round_number_ratio=0.6, fan_in_degree=20.0)
NORMAL = wf(age_days=700.0, tx_count=120, in_out_ratio=0.5, median_forward_sec=5 * 86400.0, unique_senders=4,
            round_number_ratio=0.1, fan_in_degree=1.5)
EXCHANGE_LIKE = wf(age_days=900.0, tx_count=5000, in_out_ratio=0.98, median_forward_sec=1200.0, unique_senders=800,
                   round_number_ratio=0.02, fan_in_degree=40.0)


# ---- ramp
def test_ramp_both_directions_and_clamping():
    assert ramp(5, 0, 10) == 0.5 and ramp(-3, 0, 10) == 0 and ramp(99, 0, 10) == 1
    assert ramp(15, 30, 1) == pytest.approx((15 - 30) / (1 - 30)) and ramp(0, 30, 1) == 1 and ramp(99, 30, 1) == 0


# ---- signals
def test_every_signal_is_between_0_and_1():
    for f in (MULE, COLLECTOR, NORMAL, EXCHANGE_LIKE, wf(age_days=0, tx_count=0, median_forward_sec=0)):
        assert all(0.0 <= v <= 1.0 for v in signals(f).values())


def test_signals_are_monotonic_in_their_feature():
    assert signals(wf(median_forward_sec=300))["speed"] > signals(wf(median_forward_sec=7200))["speed"]
    assert signals(wf(in_out_ratio=0.99))["passthrough"] > signals(wf(in_out_ratio=0.5))["passthrough"]
    assert signals(wf(age_days=1))["youth"] > signals(wf(age_days=15))["youth"]
    assert signals(wf(tx_count=3))["few_tx"] > signals(wf(tx_count=30))["few_tx"]
    assert signals(wf(unique_senders=30))["senders"] > signals(wf(unique_senders=5))["senders"]
    assert signals(wf(fan_in_degree=9))["fan_in"] > signals(wf(fan_in_degree=2))["fan_in"]
    assert signals(wf(round_number_ratio=0.5))["round"] > signals(wf(round_number_ratio=0.2))["round"]


def test_signal_anchor_points():
    assert signals(wf(median_forward_sec=600))["speed"] == pytest.approx(1.0)
    assert signals(wf(median_forward_sec=86400))["speed"] == pytest.approx(0.0)
    assert signals(wf(in_out_ratio=0.95))["passthrough"] == 1.0 and signals(wf(in_out_ratio=0.3))["passthrough"] == 0.0
    assert signals(wf(age_days=1))["youth"] == 1.0 and signals(wf(age_days=30))["youth"] == 0.0


# ---- score
def test_score_is_between_0_and_1():
    for f in (MULE, COLLECTOR, NORMAL, EXCHANGE_LIKE):
        assert 0.0 <= rule_score(f) <= 1.0


def test_archetypes_score_as_expected():
    assert rule_score(MULE) >= 0.75 and level_for(rule_score(MULE)) == "Critical"
    assert rule_score(COLLECTOR) >= 0.75
    assert level_for(rule_score(NORMAL)) == "Low"
    assert level_for(rule_score(EXCHANGE_LIKE)) in ("Low", "Medium")   # damped for an old, busy wallet


def test_established_wallet_is_damped():
    young = wf(age_days=5, tx_count=300, unique_senders=800, fan_in_degree=40.0, median_forward_sec=900.0,
               in_out_ratio=0.98, round_number_ratio=0.5)
    old = wf(age_days=500, tx_count=300, unique_senders=800, fan_in_degree=40.0, median_forward_sec=900.0,
             in_out_ratio=0.98, round_number_ratio=0.5)
    assert rule_score(old) == pytest.approx(rule_score(young) * rules.ESTABLISHED_DAMP, abs=1e-3)


def test_stronger_signals_never_lower_the_score():
    slow, fast = wf(age_days=0, tx_count=3, in_out_ratio=0.99, median_forward_sec=40000.0), \
        wf(age_days=0, tx_count=3, in_out_ratio=0.99, median_forward_sec=500.0)
    assert rule_score(fast) > rule_score(slow)


# ---- levels
@pytest.mark.parametrize("score,level", [(0.0, "Low"), (0.2499, "Low"), (0.25, "Medium"), (0.4999, "Medium"),
                                          (0.50, "High"), (0.7499, "High"), (0.75, "Critical"), (1.0, "Critical")])
def test_level_boundaries(score, level):
    assert level_for(score) == level


# ---- reasons
def test_reasons_for_a_mule():
    r = rule_reasons(MULE)
    assert 2 <= len(r) <= 3
    assert r[0] == "Forwards funds within 7 minutes (median)"          # the strongest signal comes first
    assert any("under a day old" in x for x in r) or any("Forwards 99%" in x for x in r)


def test_reasons_for_a_collector_quote_real_values():
    r = rule_reasons(COLLECTOR)
    assert "40 unique senders" in r and len(r) <= 3


def test_low_risk_wallet_gets_the_no_signal_line_not_an_empty_list():
    assert rule_reasons(NORMAL) == [rules.NO_SIGNAL_REASON]


def test_reasons_are_capped_and_deterministic():
    assert len(rule_reasons(MULE, k=2)) == 2 and rule_reasons(MULE) == rule_reasons(MULE)


def test_score_with_rules_bundles_level_score_reasons():
    level, score, reasons = score_with_rules(MULE)
    assert (level, score) == (level_for(rule_score(MULE)), rule_score(MULE)) and reasons == rule_reasons(MULE)


# ---- on the cached data (reported, not asserted for the real wallet)
@pytest.fixture(scope="module")
def adapter():
    return TronAdapter(offline=True)


def test_hero_pass_through_wallets_are_critical_and_deposit_address_is_a_collector(adapter):
    for addr, arrival in [("TMhTyFX8dfbnrswVFDYwoM6bXz1LjZ3ZXt", 1792400000), ("TCLZhujbkc1gBh7ZRv9BQG8M2SDVdKNscT", 1792400060)]:
        level, score, reasons = score_with_rules(extract_features(addr, adapter.transfers(addr)[0], arrival))
        assert level in ("High", "Critical") and len(reasons) >= 2, (addr, level, score, reasons)
    dep = "TAD47AKhQdrF4P8xpbVBx3GAr6Q56BFZJ3"
    assert rule_score(extract_features(dep, adapter.transfers(dep)[0])) >= 0.5


def test_real_flagged_wallet_scores_in_range(adapter):
    addr = "TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z"
    level, score, reasons = score_with_rules(extract_features(addr, adapter.transfers(addr)[0]))
    assert 0.0 <= score <= 1.0 and reasons    # reported to the user; deliberately not asserted to be High
