"""
Run the typology scenario batteries and print accuracy and what each scenario was classified as.

Run from the repo root:   python data/scripts/eval_typology_battery.py [--holdout]

DEV is the set the signatures were tuned against. --holdout runs the HOLDOUT set (different ranges): run it once at the
end, never to guide changes. All labels are our own assumptions about how each scam looks.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from engine.model.typology_battery import DEV, HOLDOUT, run  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--n", type=int, default=60)
    args = ap.parse_args()
    for label, scenarios in [("DEV", DEV)] + ([("HOLDOUT", HOLDOUT)] if args.holdout else []):
        rep = run(scenarios, n=args.n)
        mean = sum(v["accuracy"] for v in rep.values()) / len(rep)
        print(f"\n== {label}: mean accuracy {mean:.3f}")
        for name, v in rep.items():
            print(f"  {name:18} expect={v['expected']:16} acc={v['accuracy']:.2f}  {v['predicted']}")


if __name__ == "__main__":
    main()
