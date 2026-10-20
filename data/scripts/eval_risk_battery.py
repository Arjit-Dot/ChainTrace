"""
Run the simulated-scenario batteries against the risk scorer and print pass rates.

Run from the repo root:   python data/scripts/eval_risk_battery.py [--holdout] [--model path/to/risk_model.pkl]

DEV is the set we tune against. --holdout runs the HOLDOUT set (different ranges and new scenario types): run it
once at the end, never to guide changes, or it stops being an honest test. All labels are our own assumptions.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from engine.model import scoring  # noqa: E402
from engine.model.battery import DEV, HOLDOUT, run_battery, summarize  # noqa: E402
from engine.model.rules import rule_score  # noqa: E402


def show(title, report):
    print(f"\n== {title}: {summarize(report)}")
    for name, v in report.items():
        rate = "  n/a" if v["pass_rate"] is None else f"{v['pass_rate']:5.2f}"
        print(f"  {name:24} {v['kind']:12} pass={rate}  mean={v['mean_score']:.2f}  p10={v['p10']:.2f}  p90={v['p90']:.2f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--model", type=Path, default=None)
    ap.add_argument("--n", type=int, default=60)
    args = ap.parse_args()
    model = lambda f: scoring.score_wallet(f, args.model).score  # noqa: E731
    sets = [("DEV", DEV)] + ([("HOLDOUT", HOLDOUT)] if args.holdout else [])
    for label, scenarios in sets:
        show(f"{label} model", run_battery(model, scenarios, n=args.n))
        show(f"{label} rules", run_battery(rule_score, scenarios, n=args.n))


if __name__ == "__main__":
    main()
