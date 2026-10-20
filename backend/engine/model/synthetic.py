"""
Synthetic training data for the risk model (Step 6.3), plus a few seed rows from our scripted cases.

ALL OF THIS IS ASSUMPTION, NOT MEASUREMENT. The profiles below are ranges we chose for how fraud and normal wallets
tend to look. A model trained on them learns those assumptions, so its score on held-out synthetic data says how well
it learned them, not how well it detects real fraud. The three real Tether-flagged wallets are never used here.

Label 1 = fraud flow:  collector (many victims pay it) and mule (fresh wallet that passes money on).
Label 0 = not fraud:   normal user and exchange-like hub.
Each class also has a "hard" variant that looks like the other class (an aged scam wallet; a new, fast normal user),
and a few labels are flipped, so the two classes genuinely overlap and the test score is not a trivial 100%.
"""
import numpy as np
import pandas as pd

from engine.model.features import FEATURE_NAMES, NEVER_FORWARDED_SEC, WalletFeatures

PROFILES = {"collector": 1, "mule": 1, "normal": 0, "exchange_like": 0}
SHARES = {"collector": 0.20, "mule": 0.20, "normal": 0.40, "exchange_like": 0.20}
HARD_SHARE = 0.15          # of each profile, drawn from the look-alike variant
LABEL_NOISE = 0.03         # share of labels flipped
REAL_FLAGGED = {           # held out for the sanity check: never trained on
    "TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z", "TP6jUy5qZedW2KZpJfFEEAbGVyD9kQXn6k", "TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu"}


def _u(rng, lo, hi):
    return rng.uniform(lo, hi)


def _logu(rng, lo, hi):
    return float(np.exp(rng.uniform(np.log(lo), np.log(hi))))


def _row(rng, profile: str, hard: bool) -> WalletFeatures:
    if profile == "collector":
        if hard:   # an aged collector that forwards slowly
            return WalletFeatures(_u(rng, 20, 200), int(_logu(rng, 50, 500)), _u(rng, 0.5, 0.95), _logu(rng, 3600, 2 * 86400),
                                  int(_logu(rng, 8, 100)), _u(rng, 0.1, 0.5), _u(rng, 2, 20))
        return WalletFeatures(_u(rng, 0.2, 20), int(_logu(rng, 20, 400)), _u(rng, 0.8, 1.0), _logu(rng, 300, 6 * 3600),
                              int(_logu(rng, 8, 200)), _u(rng, 0.2, 0.8), _logu(rng, 3, 60))
    if profile == "mule":
        if hard:   # a mule that sat on the money for a while
            return WalletFeatures(_u(rng, 2, 40), int(_u(rng, 4, 40)), _u(rng, 0.6, 1.0), _logu(rng, 3600, 3 * 86400),
                                  int(_u(rng, 1, 4)), _u(rng, 0.2, 0.9), _u(rng, 0.3, 3))
        return WalletFeatures(_u(rng, 0, 5), int(_u(rng, 2, 15)), _u(rng, 0.9, 1.0), _logu(rng, 60, 3600),
                              int(_u(rng, 1, 3)), _u(rng, 0.4, 1.0), _u(rng, 0.3, 2))
    if profile == "normal":
        if hard:   # a new legitimate user who moved money quickly
            return WalletFeatures(_u(rng, 0, 10), int(_u(rng, 3, 30)), _u(rng, 0.7, 1.0), _logu(rng, 300, 3 * 3600),
                                  int(_u(rng, 1, 4)), _u(rng, 0.0, 0.4), _u(rng, 0.3, 3))
        return WalletFeatures(_u(rng, 30, 2000), int(_logu(rng, 10, 500)), _u(rng, 0.1, 0.9), _logu(rng, 4 * 3600, 20 * 86400),
                              int(_u(rng, 1, 15)), _u(rng, 0.0, 0.3), _u(rng, 0.3, 3))
    # exchange_like
    if hard:       # a smaller, younger exchange-style hub
        return WalletFeatures(_u(rng, 20, 200), int(_logu(rng, 100, 1500)), _u(rng, 0.8, 1.0), _logu(rng, 120, 7200),
                              int(_logu(rng, 30, 400)), _u(rng, 0.0, 0.15), _u(rng, 4, 40))
    return WalletFeatures(_u(rng, 200, 2500), int(_logu(rng, 500, 20000)), _u(rng, 0.8, 1.0), _logu(rng, 60, 7200),
                          int(_logu(rng, 100, 5000)), _u(rng, 0.0, 0.1), _logu(rng, 5, 100))


def make_synthetic(n: int = 6000, seed: int = 42) -> pd.DataFrame:
    """`n` synthetic wallets: FEATURE_NAMES columns plus label, profile, hard, source='synthetic'."""
    rng = np.random.default_rng(seed)
    rows = []
    for profile, share in SHARES.items():
        for i in range(round(n * share)):
            hard = bool(rng.random() < HARD_SHARE)
            f = _row(rng, profile, hard)
            rows.append({**f.as_dict(), "label": PROFILES[profile], "profile": profile, "hard": hard, "source": "synthetic"})
    df = pd.DataFrame(rows).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    flip = rng.random(len(df)) < LABEL_NOISE
    df.loc[flip, "label"] = 1 - df.loc[flip, "label"]
    df["flipped"] = flip
    df["median_forward_sec"] = df["median_forward_sec"].clip(upper=NEVER_FORWARDED_SEC)
    return df


def seed_rows() -> pd.DataFrame:
    """A few rows from our scripted cases (hero + the 8 scenarios), labeled by role:
    hop-1 pass-through wallets are fraud (1); wallets attribution recognised as exchange deposit addresses are not (0).
    The three real flagged wallets are never included."""
    import json

    import engine
    from contract.schemas import TraceRequest
    from engine.model.features import extract_features
    from paths import SCENARIOS_JSON

    cases = [("hero", "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo", 12000.0)]
    cases += [(s["key"], s["wallet"], s["amount"]) for s in json.loads(SCENARIOS_JSON.read_text())]
    adapter = engine._adapter()
    rows = []
    for key, wallet, amount in cases:
        t = engine.trace_complaint(TraceRequest(complaint_id=f"seed-{key}", wallet=wallet, amount=amount))
        arrival = {}
        for e in t.graph.edges:
            arrival.setdefault(e.target, e.timestamp)
        for n in t.graph.nodes:
            if n.id in REAL_FLAGGED or n.hop < 1:
                continue
            if n.type == "intermediary" and n.hop == 1:
                label = 1
            elif n.type == "exchange" and (n.label or "").endswith("(deposit address)"):
                label = 0
            else:
                continue
            f = extract_features(n.id, adapter.transfers(n.id)[0], arrival.get(n.id))
            rows.append({**f.as_dict(), "label": label, "profile": "seed", "hard": False, "source": f"seed:{key}", "flipped": False})
    return pd.DataFrame(rows, columns=FEATURE_NAMES + ["label", "profile", "hard", "source", "flipped"])
