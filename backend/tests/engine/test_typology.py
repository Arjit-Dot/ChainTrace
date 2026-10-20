"""Step 6.5: fraud typology signatures, deposit profile extraction, edge cases and the DEV scenario battery."""
import typing

import numpy as np
import pytest

import engine
from contract.schemas import Edge, Graph, Node, Typology, TraceRequest
from engine.chains.tron import TronAdapter
from engine.model.typology import (ESTABLISHED_DAYS, DepositProfile, classify, classify_wallet, deposit_profile,
                                   mixer_share)
from engine.model.typology_battery import DEV, run
from tests.support import T0, tx

W = "W"
ALLOWED = set(typing.get_args(Typology))


def P(**kw):
    base = dict(deposits=3, unique_senders=3, median_deposit=4000.0, max_deposit=5000.0, repeat_share=0.0, age_days=0.5,
                tx_count=6, median_forward_sec=600.0, forwarded_share=0.98, round_number_ratio=1.0, mixer_share=0.0)
    base.update(kw)
    return DepositProfile(**base)


# ---- each signature, and where it stops matching
def test_investment_scam():
    assert classify(P()).typology == "investment_scam"
    assert classify(P(unique_senders=1)).typology == "unknown"                      # one payer is not enough
    assert classify(P(median_deposit=400)).typology == "unknown"                    # too small for investment
    assert classify(P(median_forward_sec=2 * 86400)).typology == "unknown"          # not consolidated fast
    assert classify(P(forwarded_share=0.5)).typology == "unknown"


def test_ransomware_needs_few_large_payments_and_a_mixer():
    r = P(deposits=2, unique_senders=1, median_deposit=80000.0, mixer_share=0.6)
    assert classify(r).typology == "ransomware"
    assert classify(P(**{**r.__dict__, "mixer_share": 0.1})).typology != "ransomware"          # mixer is a side issue
    assert classify(P(**{**r.__dict__, "median_deposit": 5000.0})).typology != "ransomware"     # payments not large
    assert classify(P(**{**r.__dict__, "deposits": 9})).typology != "ransomware"                # not "a few"


def test_sextortion():
    s = P(deposits=60, unique_senders=60, median_deposit=100.0, repeat_share=0.0, round_number_ratio=0.3, median_forward_sec=30000)
    assert classify(s).typology == "sextortion"
    assert classify(P(**{**s.__dict__, "repeat_share": 0.5})).typology != "sextortion"         # the same people paying again: task
    assert classify(P(**{**s.__dict__, "unique_senders": 10})).typology != "sextortion"
    assert classify(P(**{**s.__dict__, "median_deposit": 800.0})).typology != "sextortion"


def test_task_scam():
    t = P(deposits=120, unique_senders=40, median_deposit=80.0, repeat_share=0.6, median_forward_sec=3 * 3600)
    assert classify(t).typology == "task_scam"
    assert classify(P(**{**t.__dict__, "median_forward_sec": 3 * 86400})).typology == "unknown"   # slow: no match
    assert classify(P(**{**t.__dict__, "repeat_share": 0.1})).typology == "sextortion"             # little repetition


def test_phishing():
    ph = P(deposits=2, unique_senders=2, median_deposit=3200.0, age_days=0.2, median_forward_sec=300, round_number_ratio=0.0)
    assert classify(ph).typology == "phishing"
    assert classify(P(**{**ph.__dict__, "round_number_ratio": 1.0})).typology == "investment_scam"  # round payments: investment
    assert classify(P(**{**ph.__dict__, "age_days": 10.0})).typology != "phishing"
    assert classify(P(**{**ph.__dict__, "median_forward_sec": 7200})).typology != "phishing"


def test_established_wallet_is_unknown_whatever_it_looks_like():
    assert classify(P(age_days=ESTABLISHED_DAYS)).typology == "unknown"
    assert classify(P(age_days=ESTABLISHED_DAYS - 1)).typology == "investment_scam"


def test_no_deposits_is_unknown():
    assert classify(P(deposits=0, unique_senders=0, median_deposit=0.0)).typology == "unknown"


def test_priority_ransomware_beats_investment_when_both_match():
    p = P(deposits=3, unique_senders=3, median_deposit=50000.0, mixer_share=0.5)
    assert classify(p).typology == "ransomware"


def test_every_answer_comes_with_reasons_and_is_in_the_contract_enum_and_never_darknet():
    for p in (P(), P(deposits=0), P(deposits=2, unique_senders=1, median_deposit=80000.0, mixer_share=0.6),
              P(deposits=60, unique_senders=60, median_deposit=100.0), P(age_days=500)):
        r = classify(p)
        assert r.typology in ALLOWED and r.typology != "darknet" and r.reasons and all(isinstance(x, str) for x in r.reasons)


# ---- deposit profile extraction
def test_repeat_share_and_unique_senders():
    ts = [tx("A", W, 100, T0), tx("A", W, 100, T0 + 1), tx("A", W, 100, T0 + 2), tx("B", W, 100, T0 + 3), tx("C", W, 100, T0 + 4)]
    p = deposit_profile(W, ts)
    assert p.deposits == 5 and p.unique_senders == 3 and p.repeat_share == 0.6      # A's 3 payments out of 5


def test_median_deposit_is_weighted_by_amount_so_dust_cannot_pull_it_down():
    ts = [tx("D", W, 5, T0), tx("A", W, 50000, T0 + 10), tx(W, "B", 49000, T0 + 100)]
    assert deposit_profile(W, ts).median_deposit == 50000.0
    assert deposit_profile(W, [tx("A", W, 0, T0)]).median_deposit == 0.0             # all-zero amounts do not divide by zero


def test_mixer_share_from_the_graph():
    nodes = [Node(id="V", type="victim", hop=-1), Node(id="S", type="scam_wallet", hop=0), Node(id="M", type="mixer", hop=1),
             Node(id="X", type="unknown", hop=1)]
    edges = [Edge(source="V", target="S", tx_hash="1", amount=10000.0, timestamp=1),
             Edge(source="S", target="M", tx_hash="2", amount=6000.0, timestamp=2),
             Edge(source="S", target="X", tx_hash="3", amount=4000.0, timestamp=3)]
    assert mixer_share(Graph(nodes=nodes, edges=edges)) == 0.6                        # victim payments are not counted
    assert mixer_share(None) == 0.0 and mixer_share(Graph(nodes=nodes, edges=[])) == 0.0


# ---- edge cases
@pytest.mark.parametrize("ts", [[], [tx(W, "B", 100, T0)], [tx(W, W, 100, T0)], [tx("A", W, 0, T0), tx(W, "B", 0, T0 + 5)],
                                [tx("A", W, 1e15, T0)], [tx("A", W, 1e-9, T0)], [tx("A", W, 100, T0), tx("A", W, 100, T0)]])
def test_edge_cases_never_crash_and_stay_in_the_enum(ts):
    r = classify_wallet(W, ts)
    assert r.typology in ALLOWED and r.reasons


# ---- cached data
def test_the_hero_wallet_is_classified_as_an_investment_scam():
    t = engine.trace_complaint(TraceRequest(complaint_id="C-001", wallet="TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo", amount=12000.0))
    a = TronAdapter(offline=True)
    r = classify_wallet(t.wallet, a.transfers(t.wallet)[0], t.graph)
    assert r.typology == "investment_scam" and "3 payers" in r.reasons[0]


def test_real_flagged_wallets_match_no_pattern():
    a = TronAdapter(offline=True)
    for w in ("TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z", "TP6jUy5qZedW2KZpJfFEEAbGVyD9kQXn6k", "TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu"):
        assert classify_wallet(w, a.transfers(w)[0]).typology == "unknown"


# ---- DEV battery
def test_dev_battery_is_diverse():
    names = {s.expected for s in DEV}
    assert names == {"investment_scam", "task_scam", "sextortion", "ransomware", "phishing", "unknown"} and len(DEV) >= 10


@pytest.fixture(scope="module")
def dev_report():
    return run(DEV, n=60, seed=0)


def test_dev_battery_accuracy(dev_report):
    accs = {k: v["accuracy"] for k, v in dev_report.items()}
    assert np.mean(list(accs.values())) >= 0.97 and min(accs.values()) >= 0.90, accs


def test_benign_wallets_are_called_unknown_not_a_scam_type(dev_report):
    for name in ("normal_user", "exchange_hub", "saver", "otc_trader", "charity"):
        assert dev_report[name]["predicted"].get("unknown", 0) >= 0.9, (name, dev_report[name])
