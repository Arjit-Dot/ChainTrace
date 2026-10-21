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


# Fictional lure channels. A few are SHARED between complaints on purpose, so the investigation can link them later.
SHARED = {
    "NCRP-2026-0001": {"scam_website": "hero-invest.example", "paid_to_upi": "hero.invest@okaxis"},
    "NCRP-2026-0002": {"scam_website": "https://www.hero-invest.example/app", "paid_to_upi": "hero.invest@okaxis"},
    "NCRP-2026-0003": {"scam_website": "hero-invest.example", "scammer_phone": "+91 90000 00201"},
    "NCRP-2026-0004": {"scammer_handle": "@private_pics_demo", "scammer_handle_platform": "telegram"},
    "NCRP-2026-0005": {"scammer_handle": "private_pics_demo", "scammer_handle_platform": "telegram", "scammer_phone": "+91 90000 00202"},
}
PENDING_LURES = {
    "NCRP-2026-104317": {"scammer_phone": "+91 90000 00101", "scammer_handle": "@alpha_returns_demo", "scammer_handle_platform": "telegram",
                         "scam_website": "alpha-returns.example", "paid_to_upi": "alpha.returns@ybl"},
    "NCRP-2026-258846": {"scammer_handle": "@taskpay_demo", "scammer_handle_platform": "telegram", "scam_app": "TaskPay Earn",
                         "paid_to_bank_account": "000123450001", "paid_to_ifsc": "HDFC0000001"},
    "NCRP-2026-391502": {"scammer_phone": "+91 90000 00303", "scam_website": "secure-claims.example"},
    "NCRP-2026-470218": {"scammer_handle": "@swapdesk_demo", "scammer_handle_platform": "telegram", "scam_website": "swap-desk.example"},
    "NCRP-2026-582904": {"scammer_handle": "@locker_support_demo", "scammer_handle_platform": "telegram", "scammer_phone": "+91 90000 00404"},
}
# The four demo cases, one per way the money can end (see DEMO.md). Each is waiting in the inbox for an officer to trace.
DEMO_CASES = {
    "NCRP-2026-104317": "Demo case 1 of 4, exchange (VASP): the money reaches an exchange deposit address.",
    "NCRP-2026-470218": "Demo case 2 of 4, DEX: the money is swapped on a decentralised exchange, which has no account holder.",
    "NCRP-2026-258846": "Demo case 3 of 4, mule bank account: the victim paid a bank account, and funds still sit in a wallet.",
    "NCRP-2026-582904": "Demo case 4 of 4, stalled: the money goes into a mixer and cannot be followed.",
}


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
                    "description": "Seeded demo complaint.", "stage": stage, "case_id": c["case_id"], **SHARED.get(c["complaint_id"], {}),
                    "created_at": c["reported_at"], "updated_at": h[-1]["at"], "history": h})

    scenarios = {s["key"]: s for s in json.loads(SCENARIOS_JSON.read_text())}
    real = json.loads((SCENARIOS / "real_case.json").read_text())
    pending = [
        ("NCRP-2026-104317", scenarios["sweep"]["wallet"], scenarios["sweep"]["amount"], "investment", "Karnataka", "Asha Verma"),
        ("NCRP-2026-258846", scenarios["idle"]["wallet"], scenarios["idle"]["amount"], "task", "Delhi", "Rohit Nair"),
        ("NCRP-2026-391502", real["wallet"], real["amount"], "phishing", "Maharashtra", "Meera Iyer"),
        ("NCRP-2026-470218", scenarios["dex"]["wallet"], scenarios["dex"]["amount"], "investment", "Telangana", "Karan Malhotra"),
        ("NCRP-2026-582904", scenarios["mixer"]["wallet"], scenarios["mixer"]["amount"], "ransomware", "Tamil Nadu", "Divya Reddy"),
    ]
    for j, (cid, wallet, amount, fraud, state, name) in enumerate(pending):
        created = NOW - (len(pending) - j) * 5400
        out.append({"complaint_id": cid, "wallet": wallet, "chain": "tron", "amount": amount, "fraud_type": fraud, "state": state,
                    "reporter_name": name, "reporter_mobile": mobile(20 + j), "description": DEMO_CASES.get(cid, "Waiting for an officer."), **PENDING_LURES[cid],
                    "stage": "received", "case_id": None, "created_at": created, "updated_at": created,
                    "history": history(created, "received")})
    SEED_COMPLAINTS.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {SEED_COMPLAINTS.relative_to(ROOT)}: {len(out)} complaints ({len(pending)} waiting in the inbox)")


if __name__ == "__main__":
    main()
