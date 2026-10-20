"""
Train the XGBoost risk classifier (Step 6.3) and report how it did.

Data: synthetic wallets (synthetic.py) split 75/25 by profile; seed rows from our scripted cases are added to the
TRAINING side only. The held-out 25% is never trained on. The three real flagged wallets are not used at all here.
The same held-out rows are scored with the hand-written rules (rules.py), so the report shows whether the model
beats the baseline.
"""
import platform
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
import xgboost
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from engine.model.battery import DEV, run_battery, summarize
from engine.model.features import FEATURE_NAMES, WalletFeatures
from engine.model.rules import rule_score
from engine.model.synthetic import make_synthetic, seed_rows

SEED = 42
TEST_SHARE = 0.25
THRESHOLD = 0.5   # for the accuracy / precision / recall / confusion numbers only; the app uses the probability
# Direction the score may move as a feature grows (0 = free): younger, more forwarded and faster-forwarded wallets are
# never LESS risky. This keeps explanations sensible and stops the trees from inventing odd shortcuts.
MONOTONE = {"age_days": -1, "in_out_ratio": 1, "median_forward_sec": -1}
PARAMS = dict(n_estimators=200, max_depth=4, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8,
              eval_metric="logloss", random_state=SEED, n_jobs=1,   # n_jobs=1 keeps training repeatable
              monotone_constraints=tuple(MONOTONE.get(n, 0) for n in FEATURE_NAMES))


def split(n: int = 6000, seed: int = SEED, with_seeds: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """(train, test). The test side is synthetic only and never touched by training."""
    df = make_synthetic(n, seed)
    train, test = train_test_split(df, test_size=TEST_SHARE, stratify=df["profile"], random_state=seed)
    if with_seeds:
        train = pd.concat([train, seed_rows()], ignore_index=True)
    return train.reset_index(drop=True), test.reset_index(drop=True)


def evaluate(proba: np.ndarray, test: pd.DataFrame) -> Dict[str, Any]:
    y, pred = test["label"].to_numpy(), (proba >= THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    return {
        "auc": round(float(roc_auc_score(y, proba)), 4),
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "precision": round(float(precision_score(y, pred)), 4),
        "recall": round(float(recall_score(y, pred)), 4),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "by_profile_accuracy": {p: round(float(accuracy_score(g["label"], (proba[g.index] >= THRESHOLD).astype(int))), 4)
                                for p, g in test.groupby("profile")},
    }


def _battery(scorer, n: int = 40) -> Dict[str, Any]:
    """Pass rates on the DEV scenario battery (the one we iterate on; the HOLDOUT battery is run separately, once)."""
    rep = run_battery(scorer, DEV, n=n, seed=0)
    return {**summarize(rep), "scenarios": {k: v["pass_rate"] for k, v in rep.items() if v["pass_rate"] is not None},
            "ambiguous_mean_score": {k: v["mean_score"] for k, v in rep.items() if v["pass_rate"] is None}}


def train(n: int = 6000, seed: int = SEED, with_seeds: bool = True) -> Tuple[XGBClassifier, Dict[str, Any]]:
    """Fit the model and return (model, report). The report is also what gets saved next to the model."""
    train_df, test_df = split(n, seed, with_seeds)
    model = XGBClassifier(**{**PARAMS, "random_state": seed})
    model.fit(train_df[FEATURE_NAMES].to_numpy(), train_df["label"].to_numpy())

    proba = model.predict_proba(test_df[FEATURE_NAMES].to_numpy())[:, 1]
    rules = np.array([rule_score(WalletFeatures(**row)) for row in test_df[FEATURE_NAMES].to_dict("records")])
    report = {
        "seed": seed, "xgboost": xgboost.__version__, "python": platform.python_version(),
        "features": FEATURE_NAMES,
        "rows": {"train_synthetic": int((train_df["source"] == "synthetic").sum()),
                 "train_seed": int(train_df["source"].str.startswith("seed").sum()),
                 "test_synthetic": len(test_df)},
        "positive_share_train": round(float(train_df["label"].mean()), 4),
        "model": evaluate(proba, test_df),
        "rules_baseline": evaluate(rules, test_df),
        "dev_battery": {"model": _battery(lambda f: float(model.predict_proba(np.array([f.as_list()]))[0, 1])),
                        "rules": _battery(rule_score)},
        "data_note": "Synthetic wallets from assumed ranges plus a few seed rows; the score measures how well the model "
                     "learned those assumptions, not real-world fraud detection.",
    }
    return model, report
