"""
The typology HOLDOUT battery: different ranges and new benign types from the DEV set.

Run ONCE, after the signatures were fixed against DEV; these thresholds come from that single result
(mean 0.94; ransomware_split 0.80, phishing_wide 0.82, task_big 0.87 were the weak ones: the placeholder cut-offs
for "few payments", "large payments" and "forwarded within a day" bite at the edges). Do not tune the signatures to
make this pass; if it fails something regressed, and changing it to fit would turn this into a second DEV set.
Labels are our own assumptions about how each scam looks.
"""
import numpy as np
import pytest

from engine.model.typology_battery import DEV, HOLDOUT, run


@pytest.fixture(scope="module")
def report():
    return run(HOLDOUT, n=60, seed=0)


def test_holdout_differs_from_dev():
    assert not {s.name for s in HOLDOUT} & {s.name for s in DEV}


def test_holdout_accuracy(report):
    accs = {k: v["accuracy"] for k, v in report.items()}
    assert np.mean(list(accs.values())) >= 0.90 and min(accs.values()) >= 0.75, accs


def test_the_strong_signatures_hold_on_unseen_variations(report):
    for name in ("investment_wide", "sextortion_tiny"):
        assert report[name]["accuracy"] >= 0.95, (name, report[name])


def test_benign_wallets_are_never_called_a_scam_type(report):
    for name in ("salary_account", "heavy_trader", "dca_bot", "dormant_wakes"):
        assert report[name]["predicted"].get("unknown", 0) >= 0.95, (name, report[name])
