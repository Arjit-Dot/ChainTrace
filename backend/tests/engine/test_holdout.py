"""
The HOLDOUT battery: different parameter ranges and scenario types from everything we tuned against.

It was run ONCE, after the data, rules and model were fixed against the DEV battery, and these thresholds were set
from that single result. Do not tune the model or rules to make this pass: if it fails, something regressed, and any
change made to fix it turns this file into a second DEV set. Labels are our own assumptions, so this tests robustness
to unseen variations of our scenarios, not accuracy on real fraud.
"""
import pytest

from engine.model.battery import HOLDOUT, run_battery, summarize
from engine.model.rules import rule_score
from engine.model.scoring import score_wallet


@pytest.fixture(scope="module")
def model_report():
    return run_battery(lambda f: score_wallet(f).score, HOLDOUT, n=60, seed=0)


@pytest.fixture(scope="module")
def rules_report():
    return run_battery(rule_score, HOLDOUT, n=60, seed=0)


def test_holdout_has_scenario_types_the_dev_set_lacks():
    from engine.model.battery import DEV
    assert not {s.name for s in HOLDOUT} & {s.name for s in DEV}
    assert {"hard_benign"} <= {s.kind for s in HOLDOUT}


def test_model_on_the_holdout(model_report):
    s = summarize(model_report)
    assert s["mean_pass_rate"] >= 0.95 and s["worst_rate"] >= 0.85, (s, {k: v["pass_rate"] for k, v in model_report.items()})


def test_rules_on_the_holdout(rules_report):
    s = summarize(rules_report)
    assert s["mean_pass_rate"] >= 0.95 and s["worst_rate"] >= 0.85, (s, {k: v["pass_rate"] for k, v in rules_report.items()})


def test_no_firm_scenario_is_missed_by_either_scorer(model_report, rules_report):
    for rep in (model_report, rules_report):
        for name, row in rep.items():
            if row["kind"] in ("firm_fraud", "firm_benign"):
                assert row["pass_rate"] >= 0.9, (name, row)
