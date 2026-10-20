"""
Simulated scam scenarios for judging the typology classifier (Step 6.5), built like battery.py: real transfer lists
through the real feature extraction. DEV is what we tune against; HOLDOUT (different ranges, new benign types) is run once.
Labels are OUR assumptions about how each scam looks; this tests robustness to variation, not accuracy on real cases.
"""
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import numpy as np

from engine.model.battery import DAY, HOUR, MIN, I, U, W, collector, ordinary, pass_through, idle
from engine.model.typology import classify, deposit_profile


@dataclass(frozen=True)
class TypoScenario:
    name: str
    expected: str
    build: Callable[[np.random.Generator], Tuple[list, int, float]]   # -> (transfers, arrival_ts, mixer_share)


def _plain(fn):
    """A scenario with no mixer."""
    return lambda r: (*fn(r), U(r, 0.0, 0.03))


def _dev_investment(r):
    n = I(r, 3, 40)
    return collector(r, U(r, 0, 30), n, n, (500, 20000), U(r, 0.3, 0.9), U(r, 5, 60) * MIN, I(r, 1, 3))


def _dev_task(r):
    n = I(r, 40, 300)
    return collector(r, U(r, 0, 30), n, max(10, n // I(r, 2, 5)), (20, 300), U(r, 0, 0.4), U(r, 1, 12) * HOUR, I(r, 1, 3))


def _dev_sextortion(r):
    n = I(r, 20, 300)
    return collector(r, U(r, 0, 30), n, n, (50, 200), U(r, 0, 0.5), U(r, 6, 48) * HOUR, I(r, 1, 2))


def _dev_phishing(r):
    return pass_through(r, U(r, 0, 1.5), I(r, 1, 6), I(r, 1, 6), (200, 60000), U(r, 0, 0.15),
                        lambda: U(r, MIN, 40 * MIN), lambda g: U(g, 0.9, 1.0), lambda: I(r, 1, 3))


DEV: List[TypoScenario] = [
    TypoScenario("investment", "investment_scam", _plain(_dev_investment)),
    TypoScenario("task", "task_scam", _plain(_dev_task)),
    TypoScenario("sextortion", "sextortion", _plain(_dev_sextortion)),
    TypoScenario("ransomware", "ransomware", lambda r: (*pass_through(r, U(r, 0, 40), I(r, 1, 3), 1, (15000, 500000), U(r, 0.5, 1),
                                                                      lambda: U(r, 10 * MIN, 12 * HOUR), lambda g: U(g, 0.9, 1.0), lambda: 1),
                                                       U(r, 0.4, 0.95))),
    TypoScenario("phishing", "phishing", _plain(_dev_phishing)),
    TypoScenario("normal_user", "unknown", _plain(lambda r: ordinary(r, U(r, 60, 1500), I(r, 10, 200), I(r, 1, 8), I(r, 2, 20), (5, 2000), U(r, 0, 0.5)))),
    TypoScenario("exchange_hub", "unknown", _plain(lambda r: collector(r, U(r, 300, 2500), I(r, 300, 900), I(r, 100, 600), (20, 20000), U(r, 0, 0.1),
                                                                      U(r, 0.02, 0.5) * HOUR, I(r, 2, 6)))),
    TypoScenario("saver", "unknown", _plain(lambda r: idle(r, U(r, 200, 2000), I(r, 3, 12), I(r, 1, 3), (100, 20000), U(r, 0, 0.6)))),
    TypoScenario("otc_trader", "unknown", _plain(lambda r: pass_through(r, U(r, 100, 1500), I(r, 8, 25), I(r, 2, 8), (10000, 500000), U(r, 0.7, 1),
                                                                       lambda: U(r, HOUR, 24 * HOUR), lambda g: U(g, 0.9, 1.0), lambda: I(r, 1, 3)))),
    TypoScenario("charity", "unknown", _plain(lambda r: collector(r, U(r, 100, 1500), I(r, 60, 300), I(r, 40, 250), (10, 500), U(r, 0.4, 0.9),
                                                                 U(r, 2, 20) * DAY, I(r, 1, 3)))),
]

HOLDOUT: List[TypoScenario] = [
    TypoScenario("investment_wide", "investment_scam", _plain(lambda r: (lambda n: collector(r, U(r, 0, 60), n, n, (200, 60000), U(r, 0.2, 1),
                                                                                              U(r, 3, 120) * MIN, I(r, 1, 4)))(I(r, 2, 80)))),
    TypoScenario("task_big", "task_scam", _plain(lambda r: (lambda n: collector(r, U(r, 0, 45), n, I(r, 6, 150), (10, 450), U(r, 0, 0.5),
                                                                              U(r, 1, 20) * HOUR, I(r, 1, 3)))(I(r, 60, 400)))),
    TypoScenario("sextortion_tiny", "sextortion", _plain(lambda r: (lambda n: collector(r, U(r, 0, 60), n, n, (20, 180), U(r, 0, 0.6),
                                                                                       U(r, 4, 72) * HOUR, I(r, 1, 3)))(I(r, 25, 500)))),
    TypoScenario("ransomware_split", "ransomware", lambda r: (*pass_through(r, U(r, 0, 60), I(r, 1, 5), I(r, 1, 3), (8000, 1_000_000), U(r, 0.3, 1),
                                                                            lambda: U(r, 5 * MIN, 24 * HOUR), lambda g: U(g, 0.85, 1.0), lambda: I(r, 1, 3)),
                                                             U(r, 0.25, 0.9))),
    TypoScenario("phishing_wide", "phishing", _plain(lambda r: pass_through(r, U(r, 0, 1.9), I(r, 1, 8), I(r, 1, 8), (100, 90000), U(r, 0, 0.25),
                                                                           lambda: U(r, 20, 55 * MIN), lambda g: U(g, 0.85, 1.0), lambda: I(r, 1, 4)))),
    TypoScenario("salary_account", "unknown", _plain(lambda r: ordinary(r, U(r, 100, 2000), I(r, 15, 80), 2, I(r, 5, 25), (200, 6000), U(r, 0.8, 1), 0.2,
                                                                       (6 * HOUR, 10 * DAY)))),
    TypoScenario("heavy_trader", "unknown", _plain(lambda r: ordinary(r, U(r, 200, 1500), I(r, 300, 900), I(r, 5, 30), I(r, 5, 30), (20, 30000), U(r, 0, 0.3), 0.5,
                                                                     (30, 6 * HOUR)))),
    TypoScenario("dca_bot", "unknown", _plain(lambda r: pass_through(r, U(r, 20, 500), I(r, 30, 120), 1, (100, 500), 1.0,
                                                                    lambda: U(r, 2 * HOUR, 3 * DAY), lambda g: U(g, 0.95, 1.0), lambda: 1))),
    TypoScenario("dormant_wakes", "unknown", _plain(lambda r: ordinary(r, U(r, 300, 2500), I(r, 2, 6), 2, 2, (50, 5000), U(r, 0, 0.6), 0.5, (DAY, 60 * DAY)))),
]


def run(scenarios: List[TypoScenario], n: int = 60, seed: int = 0) -> Dict[str, dict]:
    """{scenario: {expected, accuracy, predicted: {typology: share}}}."""
    import zlib
    out = {}
    for sc in scenarios:
        rng = np.random.default_rng([seed, zlib.crc32(sc.name.encode())])
        counts: Dict[str, int] = {}
        for _ in range(n):
            txs, arrival, mix = sc.build(rng)
            p = deposit_profile(W, txs, arrival)
            got = classify(type(p)(**{**p.__dict__, "mixer_share": mix})).typology
            counts[got] = counts.get(got, 0) + 1
        out[sc.name] = {"expected": sc.expected, "accuracy": round(counts.get(sc.expected, 0) / n, 3),
                        "predicted": {k: round(v / n, 2) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])}}
    return out
