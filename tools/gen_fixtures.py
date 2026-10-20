"""
Generates all fixtures in data/fixtures/ and validates each against the contract.
Run from the repo root:   python tools/gen_fixtures.py

ALL DATA IS FICTIONAL. Addresses are checksum-valid TRON addresses derived from
seed strings, and exchange/bridge/mixer names are placeholders ("Example Exchange A").
No real wallet or entity is represented.
"""
import hashlib
import json
import sys
from pathlib import Path

import base58

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from contract.schemas import (  # noqa: E402
    Alert, CaseSummary, DashboardStats, FreezeNotice, Network, TraceResponse, WalletRisk,
)

OUT = ROOT / "data" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

T0 = 1792400000  # ~ 2026-10-19 09:33 UTC, base time for the hero case


def tron(seed: str) -> str:
    raw = hashlib.sha256(seed.encode()).digest()[:20]
    return base58.b58encode_check(b"\x41" + raw).decode()


def evm(seed: str) -> str:
    return "0x" + hashlib.sha256(seed.encode()).hexdigest()[:40]


def txh(seed: str) -> str:
    return hashlib.sha256(("tx" + seed).encode()).hexdigest()


def dump(name: str, model_or_obj):
    data = model_or_obj.model_dump() if hasattr(model_or_obj, "model_dump") else model_or_obj
    (OUT / name).write_text(json.dumps(data, indent=2))
    print("wrote", name)


# ------------------------------------------------------------------ hero trace
V1, V2, V3 = tron("victim1"), tron("victim2"), tron("victim3")
S = tron("hero-scam-wallet")
I1, I2 = tron("hero-inter-1"), tron("hero-inter-2")
D1 = tron("hero-deposit-A")
H_A = tron("example-exchange-A-hot")
BR = tron("example-bridge")
MX = tron("example-mixer")
E1 = evm("hero-eth-leg")

N = lambda **k: k  # noqa: E731

nodes = [
    N(id=V1, type="victim", hop=-1, label="Victim wallet"),
    N(id=V2, type="victim", hop=-1, label="Victim wallet"),
    N(id=V3, type="victim", hop=-1, label="Victim wallet"),
    N(id=S, type="scam_wallet", hop=0, label="Reported wallet", risk="Critical", risk_score=0.96,
      reasons=["89 unique senders in 5 days", "Forwards funds within 4 minutes", "98% of inflow leaves within 1 hour"],
      typology="investment_scam"),
    N(id=I1, type="intermediary", hop=1, label="Pass-through wallet", risk="High", risk_score=0.82,
      reasons=["Forwards 99% of received funds", "Wallet age 3 days", "Only 4 lifetime transactions"],
      typology="investment_scam"),
    N(id=I2, type="intermediary", hop=1, label="Pass-through wallet", risk="High", risk_score=0.78,
      reasons=["Forwards 99% of received funds", "Funded by reported wallet only"], typology="investment_scam"),
    N(id=D1, type="exchange", hop=2, label="Example Exchange A (deposit address)", risk="Low", risk_score=0.12,
      reasons=["Behaves like an exchange deposit address"]),
    N(id=BR, type="bridge", hop=2, label="Example Bridge (TRON to Ethereum)", risk="Medium", risk_score=0.45,
      reasons=["Cross-chain bridge contract"]),
    N(id=MX, type="mixer", hop=2, label="Example Mixer", risk="Critical", risk_score=0.91,
      reasons=["Known mixing service"]),
    N(id=H_A, type="exchange", hop=3, label="Example Exchange A (hot wallet)", risk="Low", risk_score=0.05,
      reasons=["Labeled exchange hot wallet"]),
    N(id=E1, type="intermediary", hop=3, chain="ethereum", label="Ethereum-side wallet (funds still here)",
      risk="High", risk_score=0.74, reasons=["Received bridged funds", "No outflow yet"],
      typology="investment_scam", idle_balance=3720.0),
]

edges = [
    N(source=V1, target=S, tx_hash=txh("v1"), amount=5000.0, timestamp=T0 - 4000),
    N(source=V2, target=S, tx_hash=txh("v2"), amount=4000.0, timestamp=T0 - 3500),
    N(source=V3, target=S, tx_hash=txh("v3"), amount=3000.0, timestamp=T0 - 3000),
    N(source=S, target=I1, tx_hash=txh("s-i1"), amount=8000.0, timestamp=T0),
    N(source=S, target=I2, tx_hash=txh("s-i2"), amount=3800.0, timestamp=T0 + 60),
    N(source=I1, target=D1, tx_hash=txh("i1-d1"), amount=7850.0, timestamp=T0 + 420),
    N(source=I1, target=MX, tx_hash=txh("i1-mx"), amount=50.0, timestamp=T0 + 430, edge_type="mixer_in"),
    N(source=I2, target=BR, tx_hash=txh("i2-br"), amount=3750.0, timestamp=T0 + 600),
    N(source=D1, target=H_A, tx_hash=txh("d1-h"), amount=7840.0, timestamp=T0 + 1500),
    N(source=BR, target=E1, tx_hash=txh("br-e1"), amount=3720.0, timestamp=T0 + 900, edge_type="bridge"),
]

trace = {
    "case_id": "C-001",
    "complaint_id": "NCRP-2026-0001",
    "wallet": S,
    "chain": "tron",
    "fraud_type": "investment",
    "amount_lost": 12000.0,
    "risk": "Critical",
    "risk_score": 0.96,
    "typology": "investment_scam",
    "graph": {"nodes": nodes, "edges": edges},
    "nearest_vasp": {
        "vasp": "Example Exchange A",
        "deposit_address": D1,
        "hops": 2,
        "amount": 7850.0,
        "timestamp": T0 + 420,
        "confidence": 0.87,
        "method": "heuristic",
        "evidence": [
            "Deposit address received funds from 14 unrelated wallets within 72 hours",
            "It forwarded 99% of its balance to a labeled hot wallet in a single transfer",
            f"Hot wallet {H_A[:8]}... is labeled Example Exchange A (source: demo label set)",
        ],
        "contact": "compliance@example-exchange-a.test",
    },
    "summary": {"hops": 3, "nodes": 11, "total_traced": 11800.0, "idle_funds": 3720.0,
                "time_to_attribution_sec": 38.0},
    "recommendations": [
        {"priority": "urgent", "action": "Act on idle funds",
         "detail": "3,720 USDT is sitting in the Ethereum-side wallet. Request a hold from the stablecoin issuer or the next VASP before it moves."},
        {"priority": "high", "action": "Issue freeze and KYC request to Example Exchange A",
         "detail": "Deposit address received 7,850 USDT. Request freeze plus preservation of KYC, linked bank/UPI, phone and IP data."},
        {"priority": "high", "action": "Continue trace on Ethereum",
         "detail": "Funds crossed a bridge. Follow the Ethereum-side wallet for onward movement."},
        {"priority": "normal", "action": "Preserve mixer evidence",
         "detail": "50 USDT entered a mixer. Exit cannot be traced reliably; record the transaction and monitor."},
    ],
    "source": "simulated",
    "generated_at": T0 + 1600,
    "notes": "FICTIONAL demo data. Names and addresses are placeholders.",
}
dump("trace_hero.json", TraceResponse(**trace))

# ------------------------------------------------------------------ risk
dump("wallet_risk_hero.json", WalletRisk(
    address=S, risk="Critical", risk_score=0.96,
    reasons=["89 unique senders in 5 days", "Forwards funds within 4 minutes", "98% of inflow leaves within 1 hour"],
    typology="investment_scam"))

# ------------------------------------------------------------------ cases
STATES = ["Karnataka", "Maharashtra", "Delhi", "Telangana", "Tamil Nadu", "Uttar Pradesh", "Gujarat", "West Bengal"]
rows = [
    # id, amount, fraud, state, risk, status, vasp, tta, network
    ("C-001", 12000, "investment", "Karnataka", "Critical", "notice_drafted", "Example Exchange A", 38, "NET-1"),
    ("C-002", 4500, "task", "Maharashtra", "High", "attributed", "Example Exchange A", 52, "NET-1"),
    ("C-003", 9800, "investment", "Delhi", "Critical", "notice_sent", "Example Exchange A", 41, "NET-1"),
    ("C-004", 2200, "sextortion", "Telangana", "High", "attributed", "Example Exchange B", 65, "NET-2"),
    ("C-005", 1800, "sextortion", "Tamil Nadu", "High", "notice_drafted", "Example Exchange B", 58, "NET-2"),
    ("C-006", 15500, "ransomware", "Uttar Pradesh", "Critical", "unresolved", None, None, None),
    ("C-007", 3100, "phishing", "Gujarat", "Medium", "attributed", "Example Exchange C", 47, None),
    ("C-008", 6400, "task", "West Bengal", "High", "tracing", None, None, None),
]
cases = []
for i, (cid, amt, fr, st, rk, status, vasp, tta, net) in enumerate(rows, 1):
    cases.append(CaseSummary(
        case_id=cid, complaint_id=f"NCRP-2026-{i:04d}", wallet=tron(f"case-wallet-{cid}"),
        amount_lost=float(amt), fraud_type=fr, state=st, risk=rk, status=status, vasp=vasp,
        time_to_attribution_sec=tta, network_id=net, reported_at=T0 - 86400 + i * 3600))
cases[0].wallet = S  # C-001 uses the hero wallet
dump("cases.json", [c.model_dump() for c in cases])

# ------------------------------------------------------------------ dashboard
attributed = [c for c in cases if c.vasp]
tta_vals = [c.time_to_attribution_sec for c in attributed]
from collections import Counter, defaultdict  # noqa: E402

def agg(key):
    cnt, amt = Counter(), defaultdict(float)
    for c in cases:
        k = key(c)
        if k:
            cnt[k] += 1
            amt[k] += c.amount_lost
    return [{"name": k, "count": v, "amount": amt[k]} for k, v in cnt.most_common()]

dash = DashboardStats(
    total_cases=len(cases),
    total_amount_lost=sum(c.amount_lost for c in cases),
    total_amount_traced=round(sum(c.amount_lost for c in attributed) * 0.82, 2),
    vasp_identified_pct=round(100 * len(attributed) / len(cases), 1),
    avg_time_to_attribution_sec=round(sum(tta_vals) / len(tta_vals), 1),
    idle_funds_flagged=3720.0,
    by_fraud_type=agg(lambda c: c.fraud_type),
    top_vasps=agg(lambda c: c.vasp),
    by_state=agg(lambda c: c.state),
)
dump("dashboard.json", dash)

# ------------------------------------------------------------------ networks
def make_network(nid, cids, vasp, shared_label):
    shared = tron(f"{nid}-shared-deposit")
    ns = [{"id": shared, "type": "wallet", "label": shared_label},
          {"id": f"vasp-{nid}", "type": "exchange", "label": vasp}]
    es = [{"source": shared, "target": f"vasp-{nid}"}]
    amt, sts = 0.0, []
    for cid in cids:
        c = next(x for x in cases if x.case_id == cid)
        ns.append({"id": cid, "type": "complaint", "label": f"{c.complaint_id} ({c.state})"})
        es.append({"source": cid, "target": shared})
        amt += c.amount_lost
        sts.append(c.state)
    return Network(network_id=nid, complaint_ids=cids, victim_count=len(cids), total_amount=amt,
                   states=sorted(set(sts)), vasp=vasp, nodes=ns, edges=es)

dump("networks.json", [
    make_network("NET-1", ["C-001", "C-002", "C-003"], "Example Exchange A", "Shared deposit address").model_dump(),
    make_network("NET-2", ["C-004", "C-005"], "Example Exchange B", "Shared deposit address").model_dump(),
])

# ------------------------------------------------------------------ alerts
alerts = [
    Alert(id="A-1", type="FUNDS_MOVED", severity="critical", case_id="C-001",
          message="3,720 USDT moved out of the Ethereum-side wallet", timestamp=T0 + 2000),
    Alert(id="A-2", type="REACHED_VASP", severity="warning", case_id="C-002",
          message="Funds reached Example Exchange A deposit address", timestamp=T0 + 2100),
    Alert(id="A-3", type="NEW_COMPLAINT_LINKED", severity="info", case_id="C-003",
          message="New complaint linked to NET-1 (shared deposit address)", timestamp=T0 + 2200),
    Alert(id="A-4", type="ENTERED_MIXER", severity="critical", case_id="C-006",
          message="Funds entered a known mixer; trace-through is low confidence", timestamp=T0 + 2300),
]
dump("alerts.json", [a.model_dump() for a in alerts])

# ------------------------------------------------------------------ freeze notice
dump("freeze_notice_hero.json", FreezeNotice(
    case_id="C-001", to_vasp="Example Exchange A", to_email="compliance@example-exchange-a.test",
    subject="Request to freeze funds and preserve records, Complaint NCRP-2026-0001",
    body=(
        "To the Compliance / Law Enforcement Liaison Team,\n\n"
        "A cyber-fraud complaint (NCRP-2026-0001) reports the loss of 12,000 USDT. Blockchain analysis indicates "
        f"that 7,850 USDT was received at deposit address {D1} (transaction {txh('i1-d1')}) and later swept to "
        f"hot wallet {H_A}.\n\n"
        "We request that you (1) place a hold on the above funds and any related balances, and (2) preserve and share "
        "the KYC details, linked bank/UPI accounts, registered phone numbers, email addresses and login IP logs "
        "associated with this deposit address.\n\n"
        "Attribution confidence: 87% (heuristic). Evidence is attached. Legal provision references: [TO BE FILLED BY OFFICER].\n\n"
        "[Officer name / designation / contact]"),
    requested_actions=["Freeze funds", "Preserve KYC records", "Share linked bank/UPI/phone/IP data"],
))

dump("sahyog_ack.json", {"ack_id": "SAH-ACK-0001", "status": "received", "received_at": T0 + 3000, "case_id": "C-001"})
dump("ncrp_ack.json", {"ack_id": "NCRP-ACK-0001", "status": "queued", "received_at": T0 - 100, "case_id": "C-001"})

# ------------------------------------------------------------------ placeholder PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(OUT / "report_sample.pdf"), pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 790, "ChainTrace Evidence Report (SAMPLE PLACEHOLDER)")
    c.setFont("Helvetica", 11)
    for i, line in enumerate([
        "Case C-001 | Complaint NCRP-2026-0001 | Fictional demo data",
        "Replace with the real report generated by reports.py",
    ]):
        c.drawString(50, 760 - i * 18, line)
    c.save()
    print("wrote report_sample.pdf")
except Exception as e:  # reportlab optional for fixtures
    print("skipped pdf:", e)

print("ALL FIXTURES VALID")
