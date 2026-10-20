"""
Train the wallet risk model and save it to data/models/risk_model.pkl (Step 6.3).

Run from the repo root:   python data/scripts/train_risk_model.py [--rows 6000] [--seed 42]

The same seed gives the same model. Prints how it did on held-out synthetic data and how the hand-written rules
did on the same rows. The data is synthetic: read the numbers as "learned our assumptions", not "detects real fraud".
"""
import argparse
import json
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from engine.model.train import train  # noqa: E402
from paths import MODEL_PKL  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    model, report = train(args.rows, args.seed)
    MODEL_PKL.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": report["features"], "report": report}, MODEL_PKL)

    print(json.dumps({k: report[k] for k in ("rows", "positive_share_train", "model", "rules_baseline", "dev_battery")}, indent=2))
    print(f"saved {MODEL_PKL.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
