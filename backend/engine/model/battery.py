"""
A battery of simulated wallet scenarios for judging the risk scorer (Step 6.3b).

Unlike the training data (which samples the seven features directly), each scenario here builds a list of actual
TRANSFERS and runs it through `extract_features`, so feature extraction and scoring are tested together.

Two sets, written to be different from each other:
  DEV      used while fixing the data and the model: we look at these results and change things.
  HOLDOUT  different parameter ranges plus scenario types the model has never been tuned on. Run it ONCE at the
           end, never to guide changes, otherwise it stops being an honest test.

Every scenario has an expectation of what a sensible scorer should say (score = probability of fraud flow):
  firm_fraud   score >= 0.50      hard_fraud   score >= 0.25
  firm_benign  score <  0.50      hard_benign  score <  0.75
  ambiguous    no pass/fail: a wallet that really could be either from its transfers alone (reported only)
ALL LABELS ARE OUR OWN ASSUMPTIONS about how these wallets behave; this is a robustness check, not ground truth.
"""
import zlib
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import numpy as np

from engine.chains.tron import Transfer
from engine.model.features import WalletFeatures, extract_features

W = "WALLET"
DAY, HOUR, MIN = 86400, 3600, 60
T0 = 1_750_000_000
THRESHOLDS = {"firm_fraud": (">=", 0.50), "hard_fraud": (">=", 0.25), "firm_benign": ("<", 0.50), "hard_benign": ("<", 0.75)}


@dataclass(frozen=True)
class Scenario:
    name: str
    kind: str                                  # key of THRESHOLDS, or "ambiguous"
    build: Callable[[np.random.Generator], Tuple[List[Transfer], int]]   # -> (transfers, arrival_ts)


class Sim:
    """Builds one wallet's transfer list."""

    def __init__(self, rng):
        self.rng, self.txs, self.n = rng, [], 0

    def amount(self, lo, hi, round_p=0.0):
        a = float(np.exp(self.rng.uniform(np.log(lo), np.log(hi))))
        return float(max(50, round(a / 50) * 50)) if self.rng.random() < round_p else round(a, 2)

    def add(self, src, dst, amount, ts):
        self.n += 1
        self.txs.append(Transfer(f"tx{self.n}", src, dst, float(amount), int(ts)))

    def deposit(self, sender, amount, ts):
        self.add(sender, W, amount, ts)

    def pay(self, recipient, amount, ts):
        self.add(W, recipient, amount, ts)

    def history(self, age_days, first_ts):
        """A small earlier deposit so the wallet is `age_days` old when `first_ts` arrives."""
        if age_days > 0:
            self.deposit("OLD", self.amount(5, 50), first_ts - age_days * DAY)

    def result(self, arrival):
        return self.txs, int(arrival)


def U(rng, lo, hi):
    return float(rng.uniform(lo, hi))


def LU(rng, lo, hi):
    return float(np.exp(rng.uniform(np.log(lo), np.log(hi))))


def I(rng, lo, hi):  # noqa: E741
    return int(rng.integers(lo, hi + 1))


# ---------------------------------------------------------------- generic scenario shapes
def pass_through(rng, age, n_dep, senders, amt, round_p, delay, share, recipients):
    """Deposits come in and (most of) each is forwarded after a delay: mules, layering hops, bots, OTC desks."""
    s = Sim(rng)
    t = T0 + I(rng, 0, 30) * DAY
    s.history(age, t)
    first = t
    for i in range(n_dep):
        t += int(LU(rng, 30, 6 * HOUR)) if i else 0
        a = s.amount(*amt, round_p)
        s.deposit(f"S{i % senders}", a, t)
        out_t, parts = t + int(delay()), recipients()
        for r in range(parts):
            s.pay(f"R{r}", a * share(rng) / parts, out_t + r * 30)
    return s.result(first)


def collector(rng, age, n_dep, senders, amt, round_p, sweep_every, recipients, sweep_share=1.0):
    """Many different senders pay in; the wallet sweeps the pile out in lumps."""
    s = Sim(rng)
    first = t = T0 + I(rng, 0, 30) * DAY
    s.history(age, t)
    span = U(rng, 1, 10) * DAY
    pile, times = [], sorted(t + rng.uniform(0, span) for _ in range(n_dep))
    for i, ts in enumerate(times):
        a = s.amount(*amt, round_p)
        s.deposit(f"S{i % senders}", a, ts)
        pile.append(a)
    sweep_t = times[0]
    while sweep_t < times[-1] + sweep_every:
        sweep_t += sweep_every * U(rng, 0.6, 1.4)
        got = sum(a for a, ts in zip(pile, times) if ts <= sweep_t)
        sent = sum(x.amount for x in s.txs if x.from_addr == W)
        if got - sent > 0:
            for r in range(recipients):
                s.pay(f"R{r}", (got - sent) * sweep_share / recipients, sweep_t + r * 20)
    return s.result(first)


def ordinary(rng, age, n_tx, senders, recipients, amt, round_p, in_share=0.5, gap=(1 * HOUR, 5 * DAY), spend_cap=1.0):
    """Mixed in/out activity that is not linked deposit-to-forward: everyday wallets."""
    s = Sim(rng)
    first = t = T0 + I(rng, 0, 30) * DAY
    s.history(age, t)
    bal = 0.0
    for i in range(n_tx):
        t += int(LU(rng, *gap))
        if rng.random() < in_share or bal < 1:
            a = s.amount(*amt, round_p)
            s.deposit(f"S{I(rng, 0, senders - 1)}", a, t)
            bal += a
        else:
            a = min(bal * spend_cap, s.amount(*amt, round_p))
            s.pay(f"R{I(rng, 0, recipients - 1)}", a, t)
            bal -= a
    return s.result(first)


def idle(rng, age, n_dep, senders, amt, round_p):
    s = Sim(rng)
    first = t = T0 + I(rng, 0, 30) * DAY
    s.history(age, t)
    for i in range(n_dep):
        t += int(LU(rng, 60, 2 * DAY))
        s.deposit(f"S{i % senders}", s.amount(*amt, round_p), t)
    return s.result(first)


# ---------------------------------------------------------------- DEV scenarios (we iterate on these)
DEV: List[Scenario] = [
    Scenario("fast_mule", "firm_fraud", lambda r: pass_through(r, U(r, 0, 6), I(r, 1, 4), I(r, 1, 3), (500, 20000), U(r, 0, 1),
                                                              lambda: LU(r, MIN, 45 * MIN), lambda g: U(g, 0.85, 1.0), lambda: I(r, 1, 3))),
    Scenario("collector", "firm_fraud", lambda r: collector(r, U(r, 0, 40), I(r, 15, 150), I(r, 10, 150), (20, 3000), U(r, 0, 0.6),
                                                          U(r, 2, 12) * HOUR, I(r, 1, 3))),
    Scenario("splitter", "firm_fraud", lambda r: pass_through(r, U(r, 0, 10), I(r, 1, 3), 2, (5000, 80000), U(r, 0, 0.5),
                                                             lambda: LU(r, MIN, 30 * MIN), lambda g: U(g, 0.9, 1.0), lambda: I(r, 5, 30))),
    Scenario("slow_mule", "hard_fraud", lambda r: pass_through(r, U(r, 0, 15), I(r, 1, 4), I(r, 1, 3), (500, 20000), U(r, 0, 1),
                                                              lambda: LU(r, 2 * HOUR, 36 * HOUR), lambda g: U(g, 0.8, 1.0), lambda: I(r, 1, 3))),
    Scenario("aged_collector", "hard_fraud", lambda r: collector(r, U(r, 60, 300), I(r, 20, 120), I(r, 12, 100), (50, 4000), U(r, 0, 0.4),
                                                               U(r, 6, 30) * HOUR, I(r, 1, 3))),
    Scenario("normal_user", "firm_benign", lambda r: ordinary(r, U(r, 60, 1500), I(r, 10, 200), I(r, 1, 8), I(r, 2, 20), (5, 2000), U(r, 0, 0.5))),
    # a young wallet that spends part of what it receives: clearly an ordinary user
    Scenario("new_user", "firm_benign", lambda r: ordinary(r, U(r, 0, 14), I(r, 3, 25), I(r, 1, 3), I(r, 2, 8), (10, 800), U(r, 0, 0.5), 0.55,
                                                           (2 * HOUR, 3 * DAY), spend_cap=0.6)),
    # a young wallet that moves 85%+ of its money on within days looks like a slow mule from the transfers alone
    Scenario("new_user_bounce", "ambiguous", lambda r: ordinary(r, U(r, 0, 14), I(r, 3, 25), I(r, 1, 3), I(r, 2, 8), (10, 800), U(r, 0, 0.5), 0.35,
                                                                (2 * HOUR, 3 * DAY))),
    Scenario("freelancer", "firm_benign", lambda r: ordinary(r, U(r, 100, 1500), I(r, 6, 40), I(r, 2, 6), I(r, 3, 15), (300, 8000), U(r, 0.2, 0.8), 0.3,
                                                             (DAY, 20 * DAY))),
    Scenario("gamer", "firm_benign", lambda r: ordinary(r, U(r, 30, 600), I(r, 200, 800), I(r, 3, 20), I(r, 3, 20), (1, 60), U(r, 0, 0.2), 0.5,
                                                        (60, 6 * HOUR))),
    Scenario("dust_then_big_mule", "firm_fraud", lambda r: pass_through(r, U(r, 20, 120), I(r, 1, 2), 1, (5000, 60000), U(r, 0, 1),
                                                                      lambda: LU(r, 2 * MIN, 40 * MIN), lambda g: U(g, 0.9, 1.0), lambda: I(r, 1, 3))),
    Scenario("exchange_hub", "firm_benign", lambda r: collector(r, U(r, 300, 2500), I(r, 400, 1200), I(r, 100, 600), (20, 20000), U(r, 0, 0.1),
                                                              U(r, 0.02, 0.5) * HOUR, I(r, 2, 6))),
    Scenario("defi_bot", "firm_benign", lambda r: pass_through(r, U(r, 30, 400), I(r, 100, 500), I(r, 1, 4), (100, 50000), U(r, 0, 0.2),
                                                              lambda: LU(r, 5, 600), lambda g: U(g, 0.9, 1.0), lambda: I(r, 1, 3))),
    Scenario("otc_trader", "firm_benign", lambda r: pass_through(r, U(r, 100, 1500), I(r, 8, 25), I(r, 2, 8), (10000, 500000), U(r, 0.7, 1),
                                                                lambda: LU(r, HOUR, 24 * HOUR), lambda g: U(g, 0.9, 1.0), lambda: I(r, 1, 3))),
    Scenario("saver", "firm_benign", lambda r: idle(r, U(r, 200, 2000), I(r, 3, 12), I(r, 1, 3), (100, 20000), U(r, 0, 0.6))),
    Scenario("charity", "firm_benign", lambda r: collector(r, U(r, 100, 1500), I(r, 60, 300), I(r, 40, 250), (10, 500), U(r, 0.4, 0.9),
                                                         U(r, 2, 20) * DAY, I(r, 1, 3))),
    Scenario("merchant", "ambiguous", lambda r: collector(r, U(r, 100, 800), I(r, 50, 300), I(r, 50, 300), (5, 200), U(r, 0, 0.3),
                                                        U(r, 6, 30) * HOUR, 1)),
    Scenario("idle_collector", "ambiguous", lambda r: idle(r, U(r, 0, 30), I(r, 15, 100), I(r, 10, 80), (20, 2000), U(r, 0, 0.6))),
    Scenario("fresh_idle_wallet", "ambiguous", lambda r: idle(r, 0, 1, 1, (100, 20000), U(r, 0, 1))),
]

# ---------------------------------------------------------------- HOLDOUT (different ranges, new types: run once)
HOLDOUT: List[Scenario] = [
    Scenario("fast_mule_wide", "firm_fraud", lambda r: pass_through(r, U(r, 0, 25), I(r, 1, 6), I(r, 1, 6), (50, 60000), U(r, 0, 1),
                                                                   lambda: LU(r, 5 * MIN, 4 * HOUR), lambda g: U(g, 0.7, 1.0), lambda: I(r, 1, 4))),
    Scenario("layering_hop", "firm_fraud", lambda r: pass_through(r, U(r, 0, 20), I(r, 1, 5), 1, (2000, 90000), U(r, 0, 0.7),
                                                                 lambda: LU(r, 10 * MIN, 90 * MIN), lambda g: U(g, 0.92, 1.0), lambda: 2)),
    Scenario("phishing_receiver", "firm_fraud", lambda r: pass_through(r, U(r, 0, 3), I(r, 3, 30), I(r, 3, 30), (1000, 100000), U(r, 0, 0.3),
                                                                      lambda: LU(r, MIN, 20 * MIN), lambda g: U(g, 0.9, 1.0), lambda: I(r, 1, 3))),
    Scenario("romance_mule", "hard_fraud", lambda r: pass_through(r, U(r, 0, 5), I(r, 1, 4), I(r, 1, 2), (1000, 50000), U(r, 0.8, 1),
                                                                 lambda: LU(r, HOUR, 6 * HOUR), lambda g: U(g, 0.85, 1.0), lambda: I(r, 1, 2))),
    Scenario("sextortion_collector", "hard_fraud", lambda r: collector(r, U(r, 0, 60), I(r, 30, 300), I(r, 30, 300), (30, 600), U(r, 0.3, 0.9),
                                                                      U(r, 6, 48) * HOUR, I(r, 1, 2))),
    Scenario("big_collector", "firm_fraud", lambda r: collector(r, U(r, 0, 20), I(r, 100, 400), I(r, 60, 400), (50, 9000), U(r, 0, 0.5),
                                                              U(r, 1, 6) * HOUR, I(r, 1, 4))),
    Scenario("salary_account", "firm_benign", lambda r: ordinary(r, U(r, 100, 2000), I(r, 15, 80), 2, I(r, 5, 25), (200, 6000), U(r, 0.8, 1), 0.2,
                                                                (6 * HOUR, 10 * DAY))),
    Scenario("dca_bot", "firm_benign", lambda r: pass_through(r, U(r, 20, 500), I(r, 30, 120), 1, (100, 500), 1.0,
                                                             lambda: LU(r, 2 * HOUR, 3 * DAY), lambda g: U(g, 0.95, 1.0), lambda: 1)),
    Scenario("dormant_wakes", "firm_benign", lambda r: ordinary(r, U(r, 300, 2500), I(r, 2, 6), 2, 2, (50, 5000), U(r, 0, 0.6), 0.5, (DAY, 60 * DAY))),
    Scenario("heavy_trader", "firm_benign", lambda r: ordinary(r, U(r, 200, 1500), I(r, 300, 900), I(r, 5, 30), I(r, 5, 30), (20, 30000), U(r, 0, 0.3), 0.5,
                                                              (30, 6 * HOUR))),
    Scenario("p2p_trader", "hard_benign", lambda r: collector(r, U(r, 60, 800), I(r, 100, 400), I(r, 50, 300), (20, 3000), U(r, 0.2, 0.6),
                                                            U(r, 10, 300) * MIN, I(r, 5, 40))),
    Scenario("airdrop_farmer", "ambiguous", lambda r: collector(r, U(r, 0, 20), I(r, 20, 200), I(r, 20, 200), (1, 30), U(r, 0, 0.2), U(r, 1, 6) * HOUR, 1)),
    Scenario("new_wallet_one_deposit", "ambiguous", lambda r: idle(r, U(r, 0, 3), I(r, 1, 3), 1, (50, 5000), U(r, 0, 1))),
]


# ---------------------------------------------------------------- running it
def instances(scenario: Scenario, n: int, seed: int) -> List[WalletFeatures]:
    rng = np.random.default_rng([seed, zlib.crc32(scenario.name.encode())])
    out = []
    for _ in range(n):
        txs, arrival = scenario.build(rng)
        out.append(extract_features(W, txs, arrival))
    return out


def passes(kind: str, score: float) -> bool:
    op, thr = THRESHOLDS[kind]
    return score >= thr if op == ">=" else score < thr


def run_battery(scorer: Callable[[WalletFeatures], float], scenarios: List[Scenario], n: int = 60, seed: int = 0) -> Dict[str, dict]:
    """{scenario: {kind, pass_rate (None if ambiguous), mean_score, p10, p90}} for a scorer that maps features -> 0-1."""
    report = {}
    for sc in scenarios:
        feats = instances(sc, n, seed)
        scores = np.array([scorer(f) for f in feats])
        report[sc.name] = {
            "kind": sc.kind,
            "pass_rate": None if sc.kind == "ambiguous" else round(float(np.mean([passes(sc.kind, s) for s in scores])), 3),
            "mean_score": round(float(scores.mean()), 3),
            "p10": round(float(np.percentile(scores, 10)), 3),
            "p90": round(float(np.percentile(scores, 90)), 3),
        }
    return report


def summarize(report: Dict[str, dict]) -> Dict[str, float]:
    """Mean pass rate over the scored scenarios, and the worst one."""
    rates = {k: v["pass_rate"] for k, v in report.items() if v["pass_rate"] is not None}
    worst = min(rates, key=rates.get)
    return {"mean_pass_rate": round(float(np.mean(list(rates.values()))), 3), "worst": worst, "worst_rate": rates[worst]}
