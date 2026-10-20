"""
Synthetic training data for the risk model (Step 6.3), plus a few seed rows from our scripted cases.

ALL OF THIS IS ASSUMPTION, NOT MEASUREMENT. The profiles below are ranges we chose for how fraud and normal wallets
tend to look. A model trained on them learns those assumptions, so its score on held-out synthetic data says how well
it learned them, not how well it detects real fraud. The three real Tether-flagged wallets are never used here.

Label 1 = fraud flow:  fast/slow mule, collector, splitter.
Label 0 = not fraud:   normal and new users, exchange hub, bot, OTC desk, saver, charity/merchant.
Profile ranges are wide and overlap, no single feature (round amounts, age, ...) separates the classes on its own,
and a few labels are flipped, so the classes genuinely overlap and the test score is not a trivial 100%.
"""
import numpy as np
import pandas as pd

from engine.model.features import FEATURE_NAMES, NEVER_FORWARDED_SEC, WalletFeatures

# profile -> (label, share of the data). Fraud flows are 40%.
PROFILES = {
    "fast_mule": (1, 0.14), "slow_mule": (1, 0.08), "collector": (1, 0.12), "splitter": (1, 0.06),
    "normal_user": (0, 0.16), "new_user": (0, 0.10), "exchange_hub": (0, 0.08), "defi_bot": (0, 0.08),
    "otc_trader": (0, 0.06), "saver": (0, 0.06), "charity_merchant": (0, 0.06),
}
LABEL_NOISE = 0.03         # share of labels flipped
REAL_FLAGGED = {           # held out for the sanity check: never trained on
    "TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z", "TP6jUy5qZedW2KZpJfFEEAbGVyD9kQXn6k", "TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu"}


def _ll(rng, lo, hi):
    """Log-uniform: spreads values across orders of magnitude (seconds to days, tens to thousands of tx)."""
    return float(np.exp(rng.uniform(np.log(lo), np.log(hi))))


def _u(rng, lo, hi):
    return float(rng.uniform(lo, hi))


def _round_share(rng, a, b):
    """Round-amount share. Beta draws keep it spread out and only weakly tied to the class (it must not be a shortcut)."""
    return float(rng.beta(a, b))


def _mixed_age(rng, young, mid, old, p_young, p_mid):
    r = rng.random()
    return _u(rng, *young) if r < p_young else _u(rng, *mid) if r < p_young + p_mid else _ll(rng, *old)


def _features(rng, age, senders, recipients, tx, in_out, forward, rnd) -> WalletFeatures:
    return WalletFeatures(age_days=max(0.0, age), tx_count=max(1, int(tx)), in_out_ratio=min(1.0, max(0.0, in_out)),
                          median_forward_sec=min(float(NEVER_FORWARDED_SEC), max(1.0, forward)),
                          unique_senders=max(1, int(senders)), round_number_ratio=min(1.0, max(0.0, rnd)),
                          fan_in_degree=max(1, int(senders)) / max(1, int(recipients)))


def _row(rng, profile: str) -> WalletFeatures:
    """One wallet of a profile. Ranges are wide and overlap between profiles on purpose."""
    if profile == "fast_mule":
        s, r = int(_u(rng, 1, 7)), int(_u(rng, 1, 5))
        return _features(rng, _mixed_age(rng, (0, 7), (7, 60), (60, 400), 0.7, 0.25), s, r, _ll(rng, 2, 30), _u(rng, 0.75, 1.0),
                         _ll(rng, 30, 8 * 3600), _round_share(rng, 1.3, 1.7))
    if profile == "slow_mule":
        s, r = int(_u(rng, 1, 5)), int(_u(rng, 1, 4))
        return _features(rng, _u(rng, 0, 30), s, r, _ll(rng, 3, 40), _u(rng, 0.6, 1.0), _ll(rng, 3600, 3 * 86400), _round_share(rng, 1.3, 1.7))
    if profile == "collector":
        s, r = int(_ll(rng, 8, 300)), int(_u(rng, 1, 5))
        return _features(rng, _mixed_age(rng, (0, 20), (20, 80), (80, 500), 0.5, 0.3), s, r, s * _u(rng, 1.0, 3.0) + _u(rng, 0, 20),
                         _u(rng, 0.6, 1.0), _ll(rng, 300, 36 * 3600), _round_share(rng, 1.2, 2.0))
    if profile == "splitter":
        s, r = int(_u(rng, 1, 5)), int(_u(rng, 5, 31))
        return _features(rng, _u(rng, 0, 25), s, r, s + r + _u(rng, 0, 5), _u(rng, 0.85, 1.0), _ll(rng, 60, 2400), _round_share(rng, 1.3, 1.7))
    if profile == "normal_user":
        s, r = int(_u(rng, 1, 11)), int(_u(rng, 2, 21))
        return _features(rng, _ll(rng, 20, 2000), s, r, _ll(rng, 8, 300), _u(rng, 0.1, 0.9), _ll(rng, 3 * 3600, 30 * 86400), _round_share(rng, 1.1, 2.5))
    if profile == "new_user":
        s, r = int(_u(rng, 1, 5)), int(_u(rng, 1, 9))
        return _features(rng, _u(rng, 0, 20), s, r, _ll(rng, 3, 30), _u(rng, 0.1, 0.85), _ll(rng, 3 * 3600, 10 * 86400), _round_share(rng, 1.2, 2.0))
    if profile == "exchange_hub":
        s, r = int(_ll(rng, 80, 3000)), int(_ll(rng, 15, 300))
        return _features(rng, _ll(rng, 150, 2500), s, r, _ll(rng, 300, 20000), _u(rng, 0.85, 1.0), _ll(rng, 60, 3 * 3600), _round_share(rng, 1.0, 12))
    if profile == "defi_bot":
        s, r = int(_u(rng, 1, 7)), int(_u(rng, 1, 7))
        return _features(rng, _ll(rng, 10, 500), s, r, _ll(rng, 80, 1500), _u(rng, 0.85, 1.0), _ll(rng, 3, 900), _round_share(rng, 1.2, 3.0))
    if profile == "otc_trader":
        s, r = int(_u(rng, 1, 11)), int(_u(rng, 1, 9))
        return _features(rng, _ll(rng, 60, 1500), s, r, _ll(rng, 6, 60), _u(rng, 0.8, 1.0), _ll(rng, 1800, 36 * 3600), _round_share(rng, 4.0, 1.3))
    if profile == "saver":
        s, r = int(_u(rng, 1, 5)), int(_u(rng, 1, 3))
        return _features(rng, _ll(rng, 100, 2000), s, r, _ll(rng, 2, 15), _u(rng, 0.0, 0.3),
                         _ll(rng, 86400, NEVER_FORWARDED_SEC), _round_share(rng, 1.2, 1.8))
    # charity_merchant: many small payers, slow consolidation
    s, r = int(_ll(rng, 30, 400)), int(_u(rng, 1, 4))
    return _features(rng, _ll(rng, 60, 1500), s, r, s * _u(rng, 1.0, 2.5), _u(rng, 0.5, 1.0), _ll(rng, 6 * 3600, 20 * 86400), _round_share(rng, 2.0, 2.0))


def make_synthetic(n: int = 6000, seed: int = 42) -> pd.DataFrame:
    """`n` synthetic wallets: FEATURE_NAMES columns plus label, profile, source='synthetic', flipped."""
    rng = np.random.default_rng(seed)
    rows = []
    for profile, (label, share) in PROFILES.items():
        for _ in range(round(n * share)):
            rows.append({**_row(rng, profile).as_dict(), "label": label, "profile": profile, "source": "synthetic"})
    df = pd.DataFrame(rows).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    flip = rng.random(len(df)) < LABEL_NOISE
    df.loc[flip, "label"] = 1 - df.loc[flip, "label"]
    df["flipped"] = flip
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
            rows.append({**f.as_dict(), "label": label, "profile": "seed", "source": f"seed:{key}", "flipped": False})
    return pd.DataFrame(rows, columns=FEATURE_NAMES + ["label", "profile", "source", "flipped"])
