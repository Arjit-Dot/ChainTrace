"""
Rule-based wallet risk (Step 6.2): a hand-written score over the seven features.

This is the baseline and the fallback when the trained model is unavailable. Every number below is a
PLACEHOLDER chosen from how fraud flows usually look, to be tuned by investigators.

Two archetypes, because fraud wallets look different depending on their job:
  mule       a fresh wallet that takes money in and passes it on at once (fast, ~all forwarded, young, few txs)
  collector  a wallet many victims pay, which consolidates it (many senders, many-to-few, fast, round amounts)
The score is the stronger of the two, halved for an old, busy wallet (that looks like normal use).
"""
import math
from typing import Dict, List, Tuple

from engine.model.features import WalletFeatures

# ---- placeholders ---------------------------------------------------------------------------------------
LEVEL_CUTOFFS = [(0.75, "Critical"), (0.50, "High"), (0.25, "Medium")]   # else "Low"
MULE_WEIGHTS = {"speed": 0.40, "passthrough": 0.25, "youth": 0.20, "few_tx": 0.15}
COLLECTOR_WEIGHTS = {"senders": 0.40, "fan_in": 0.25, "speed": 0.20, "round": 0.15}
FAST_SEC, SLOW_SEC = 600, 86400          # forwards within 10 min = fully suspicious, a day or more = not at all
PASS_THROUGH = (0.30, 0.95)              # in/out ratio: 0.30 and below = 0, 0.95 and above = 1
YOUNG_DAYS = (30.0, 1.0)                 # age: 30 days and above = 0, a day or less = 1
FEW_TX = (50, 4)                         # transfer count: 50 and above = 0, 4 or fewer = 1
MANY_SENDERS = (1, 20)                   # unique senders: 1 = 0, 20 and above = 1
FAN_IN = (1.0, 10.0)                     # senders per recipient: 1 = 0, 10 and above = 1
ROUND_SHARE = (0.10, 0.50)               # share of round amounts: 10% = 0, 50% and above = 1
ESTABLISHED = {"min_tx": 200, "min_age_days": 90}   # old and busy: damp the score
ESTABLISHED_DAMP = 0.5
REASON_MIN = 0.5                         # a signal must reach this to be quoted as a reason
NO_SIGNAL_REASON = "No strong fraud signals"


def ramp(x: float, zero_at: float, one_at: float) -> float:
    """0 at `zero_at`, 1 at `one_at`, linear between, clamped. Works in either direction."""
    return min(1.0, max(0.0, (x - zero_at) / (one_at - zero_at)))


def signals(f: WalletFeatures) -> Dict[str, float]:
    """Each feature as a 0-1 'how suspicious' signal."""
    return {
        "speed": ramp(math.log(max(f.median_forward_sec, 1)), math.log(SLOW_SEC), math.log(FAST_SEC)),
        "passthrough": ramp(f.in_out_ratio, *PASS_THROUGH),
        "youth": ramp(f.age_days, *YOUNG_DAYS),
        "few_tx": ramp(f.tx_count, *FEW_TX),
        "senders": ramp(f.unique_senders, *MANY_SENDERS),
        "fan_in": ramp(f.fan_in_degree, *FAN_IN),
        "round": ramp(f.round_number_ratio, *ROUND_SHARE),
    }


def _weighted(weights: Dict[str, float], s: Dict[str, float]) -> float:
    return sum(w * s[k] for k, w in weights.items())


def rule_score(f: WalletFeatures) -> float:
    """0-1 risk score: the stronger archetype, damped for an established wallet."""
    s = signals(f)
    score = max(_weighted(MULE_WEIGHTS, s), _weighted(COLLECTOR_WEIGHTS, s))
    if f.tx_count >= ESTABLISHED["min_tx"] and f.age_days >= ESTABLISHED["min_age_days"]:
        score *= ESTABLISHED_DAMP
    return round(score, 4)


def level_for(score: float) -> str:
    """Low / Medium / High / Critical from a 0-1 score."""
    return next((name for cutoff, name in LEVEL_CUTOFFS if score >= cutoff), "Low")


def _sentence(key: str, f: WalletFeatures) -> str:
    if key == "speed":
        return f"Forwards funds within {_duration(f.median_forward_sec)} (median)"
    if key == "passthrough":
        return f"Forwards {f.in_out_ratio:.0%} of what it receives"
    if key == "youth":
        return "Wallet was under a day old when funds arrived" if f.age_days < 1 else \
            f"Wallet was only {f.age_days:.0f} days old when funds arrived"
    if key == "few_tx":
        return f"Only {f.tx_count} lifetime transactions"
    if key == "senders":
        return f"{f.unique_senders} unique senders"
    if key == "fan_in":
        return f"Many-to-few consolidation ({f.fan_in_degree:.1f} senders per recipient)"
    return f"{f.round_number_ratio:.0%} of transfers are round amounts"


def _duration(sec: float) -> str:
    if sec < 3600:
        return f"{max(1, round(sec / 60))} minutes"
    if sec < 2 * 86400:
        return f"{sec / 3600:.0f} hours"
    return f"{sec / 86400:.0f} days"


def rule_reasons(f: WalletFeatures, k: int = 3) -> List[str]:
    """Up to k readable reasons, strongest first. Only signals of the winning archetype that reach REASON_MIN
    are quoted; a wallet with none gets a single 'no strong signals' line so the list is never empty."""
    s = signals(f)
    weights = MULE_WEIGHTS if _weighted(MULE_WEIGHTS, s) >= _weighted(COLLECTOR_WEIGHTS, s) else COLLECTOR_WEIGHTS
    ranked = sorted(((w * s[key], key) for key, w in weights.items() if s[key] >= REASON_MIN), reverse=True)
    return [_sentence(key, f) for _, key in ranked[:k]] or [NO_SIGNAL_REASON]


def score_with_rules(f: WalletFeatures) -> Tuple[str, float, List[str]]:
    """(risk level, risk score, reasons) from the rules alone."""
    score = rule_score(f)
    return level_for(score), score, rule_reasons(f)
