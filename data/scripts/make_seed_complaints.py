"""
Seed complaints for the officer inbox (portal stage 2), written to data/seed/seed_complaints.json.

  - one complaint per seeded case (NCRP-2026-0001..0008), already past the inbox: investigating, or action initiated
  - a few NEW complaints waiting in the inbox, on wallets the engine can trace from the cache, so a demo can trigger
    the trace live

ALL NAMES AND NUMBERS ARE FICTIONAL. Run from the repo root:   python data/scripts/make_seed_complaints.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from paths import SCENARIOS, SCENARIOS_JSON, SEED_CASES, SEED_COMPLAINTS  # noqa: E402

NAMES = ["Asha Verma", "Rohit Nair", "Meera Iyer", "Karan Malhotra", "Divya Reddy", "Imran Sheikh", "Neha Kulkarni",
         "Suresh Babu", "Anita Das", "Vikram Singh", "Pooja Mehta", "Arun Menon"]
NOW = 1_792_540_000            # a fixed "today" (2026-10-21) so the seed is reproducible
STAGE_FOR = {"notice_sent": "action_initiated"}          # every other case status means the investigation is under way


def mobile(i: int) -> str:
    return f"98{(7_300_000 + i * 83_117) % 100_000_000:08d}"


def history(created, stage):
    steps = [("received", "Complaint registered")]
    if stage != "received":
        steps += [("under_review", "Opened for review by an officer"), ("investigating", "Trace triggered")]
    if stage == "action_initiated":
        steps.append(("action_initiated", "Report issued and freeze request sent"))
    return [{"at": created + 1800 * i, "stage": st, "note": note} for i, (st, note) in enumerate(steps)]


def main():
    cases = json.loads(SEED_CASES.read_text())
    out = []
    for i, c in enumerate(cases):
        stage = STAGE_FOR.get(c["status"], "investigating")
        h = history(c["reported_at"], stage)
        out.append({"complaint_id": c["complaint_id"], "wallet": c["wallet"], "chain": "tron", "amount": c["amount_lost"],
                    "fraud_type": c["fraud_type"], "state": c["state"], "reporter_name": NAMES[i], "reporter_mobile": mobile(i),
                    "description": "Seeded demo complaint.", "stage": stage, "case_id": c["case_id"],
                    "created_at": c["reported_at"], "updated_at": h[-1]["at"], "history": h})

    scenarios = {s["key"]: s for s in json.loads(SCENARIOS_JSON.read_text())}
    real = json.loads((SCENARIOS / "real_case.json").read_text())
    pending = [
        ("NCRP-2026-104317", scenarios["sweep"]["wallet"], scenarios["sweep"]["amount"], "investment", "Karnataka", "Asha Verma"),
        ("NCRP-2026-258846", scenarios["idle"]["wallet"], scenarios["idle"]["amount"], "task", "Delhi", "Rohit Nair"),
        ("NCRP-2026-391502", real["wallet"], real["amount"], "phishing", "Maharashtra", "Meera Iyer"),
    ]
    for j, (cid, wallet, amount, fraud, state, name) in enumerate(pending):
        created = NOW - (3 - j) * 5400
        out.append({"complaint_id": cid, "wallet": wallet, "chain": "tron", "amount": amount, "fraud_type": fraud, "state": state,
                    "reporter_name": name, "reporter_mobile": mobile(20 + j), "description": "Waiting for an officer.",
                    "stage": "received", "case_id": None, "created_at": created, "updated_at": created,
                    "history": history(created, "received")})
    SEED_COMPLAINTS.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {SEED_COMPLAINTS.relative_to(ROOT)}: {len(out)} complaints ({len(pending)} waiting in the inbox)")


if __name__ == "__main__":
    main()
