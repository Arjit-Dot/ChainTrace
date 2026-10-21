"""
Score a wallet (Step 6.4): trained model probability -> risk level, with SHAP reasons.

score_wallet() uses the trained model when data/models/risk_model.pkl loads and matches the feature list;
otherwise it falls back to the hand-written rules (rules.py), so a trace never fails for want of a model.
The risk_score is the model's probability of "fraud flow" (0-1); the level cut-offs are shared with the rules.
"""
import functools
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np
import shap

from engine.model.features import FEATURE_NAMES, WalletFeatures
from engine.model.rules import NO_SIGNAL_REASON, duration_text, level_for, score_with_rules
from paths import MODEL_PKL

log = logging.getLogger(__name__)
MAX_REASONS = 3
MIN_SHAP = 0.15        # a feature must push the score up by at least this (log-odds) to be quoted
STRONG_LEVELS = {"High", "Critical"}
THIN_CAP = 0.45                      # a wallet with too little history is never scored above Medium
TRUNCATED_CAP = THIN_CAP             # same cap for a wallet whose history we only partly fetched
THIN_REASON = "Too little transaction history to judge"
TRUNCATED_REASON = "Only the latest transfers were fetched, so its age and activity level are unreliable"
NO_HISTORY_REASON = "No transaction history found"


@dataclass(frozen=True)
class RiskScore:
    level: str
    score: float
    reasons: List[str]
    method: str        # "model" or "rules"


@functools.lru_cache(maxsize=4)
def _load(path: str):
    """(model, SHAP explainer) or None when the file is missing, unreadable or built for other features."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        bundle = joblib.load(p)
        if bundle["features"] != FEATURE_NAMES:
            log.warning("risk model %s was trained on different features; using rules", p)
            return None
        return bundle["model"], shap.TreeExplainer(bundle["model"])
    except Exception as exc:  # corrupt file, version mismatch...
        log.warning("could not load risk model %s (%s); using rules", p, exc)
        return None


def load_model(path: Path = None):
    return _load(str(path or MODEL_PKL))


def sentence(name: str, f: WalletFeatures) -> str:
    """A true, readable description of one feature's value (the SHAP step decides which ones to quote)."""
    if name == "age_days":
        return "Wallet was under a day old when funds arrived" if f.age_days < 1 else \
            f"Wallet was {f.age_days:.0f} days old when funds arrived"
    if name == "tx_count":
        return f"Only {f.tx_count} lifetime transactions" if f.tx_count <= 10 else f"{f.tx_count} lifetime transactions"
    if name == "in_out_ratio":
        return f"Forwards {f.in_out_ratio:.0%} of what it receives"
    if name == "median_forward_sec":
        d = duration_text(f.median_forward_sec)
        return f"Forwards funds within {d} (median)" if f.median_forward_sec < 3600 else f"Median time to forward funds is {d}"
    if name == "unique_senders":
        return "Funded by a single wallet" if f.unique_senders == 1 else f"{f.unique_senders} unique senders"
    if name == "round_number_ratio":
        return f"{f.round_number_ratio:.0%} of transfers are round amounts"
    return f"{f.fan_in_degree:.1f} senders per recipient (consolidation)"


def shap_reasons(explainer, f: WalletFeatures, level: str, k: int = MAX_REASONS, exclude=()) -> List[str]:
    """The features that pushed this wallet's score toward fraud the most, as sentences with the real values."""
    if level == "Low":                                    # nothing worth flagging: do not quote features
        return [NO_SIGNAL_REASON]
    contrib = explainer.shap_values(np.array([f.as_list()]))[0]
    ranked = sorted(((c, n) for c, n in zip(contrib, FEATURE_NAMES) if c > 0 and n not in exclude), reverse=True)
    picked = [n for c, n in ranked if c >= MIN_SHAP][:k]
    if level in STRONG_LEVELS and len(picked) < 2:        # a High/Critical wallet always shows at least 2 reasons
        picked = [n for _, n in ranked][:2]
    return [sentence(n, f) for n in picked] or [NO_SIGNAL_REASON]


def thin_history(f: WalletFeatures) -> bool:
    """Too little behaviour to judge: a single transfer, or a few that only ever came IN (nothing was forwarded)."""
    return f.tx_count < 2 or (f.in_out_ratio == 0 and f.tx_count <= 3)


TRUNCATED_UNRELIABLE = ("age_days", "tx_count")   # a partly fetched history misstates these two


def score_wallet(f: WalletFeatures, model_path: Optional[Path] = None, truncated: bool = False) -> RiskScore:
    """Risk level, 0-1 score and reasons for one wallet's features.

    `truncated`: only the newest part of the wallet's history was fetched (see TronAdapter.history_truncated).
    Age and transfer count are then unreliable, so the score is capped at Medium and those two are never quoted."""
    if f.tx_count == 0:
        return RiskScore("Low", 0.0, [NO_HISTORY_REASON], "none")
    if thin_history(f):                                   # cannot show pass-through behaviour yet: cap, do not guess
        inner = _score(f, model_path)
        score = min(inner.score, THIN_CAP)
        return RiskScore(level_for(score), score, [THIN_REASON], inner.method)
    if truncated:
        inner = _score(f, model_path, exclude=TRUNCATED_UNRELIABLE)
        score = min(inner.score, TRUNCATED_CAP)
        others = [r for r in inner.reasons if r != NO_SIGNAL_REASON]
        return RiskScore(level_for(score), score, [TRUNCATED_REASON] + others[:MAX_REASONS - 1], inner.method)
    return _score(f, model_path)


def _score(f: WalletFeatures, model_path: Optional[Path], exclude=()) -> RiskScore:
    loaded = load_model(model_path)
    if loaded is None:
        level, score, reasons = score_with_rules(f, exclude=tuple({"age_days": "youth", "tx_count": "few_tx"}[e] for e in exclude))
        return RiskScore(level, score, reasons, "rules")
    model, explainer = loaded
    score = round(float(model.predict_proba(np.array([f.as_list()]))[0, 1]), 4)
    level = level_for(score)
    return RiskScore(level, score, shap_reasons(explainer, f, level, exclude=exclude), "model")
