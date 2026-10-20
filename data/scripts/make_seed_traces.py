"""
Builds data/seed/seed_traces.json: one pre-built TraceResponse per seed case (Person B).

Run from the repo root:   python data/scripts/make_seed_traces.py

The dashboard, case list and Network View read these, so they never wait on the engine.
ALL DATA IS FICTIONAL. Addresses use the same seed-string scheme as data/scripts/gen_fixtures.py,
so they line up with data/fixtures/ (C-001 is trace_hero.json, unchanged).

Coverage: NET-1 (C-001/2/3) shares the Example Exchange A deposit address, NET-2 (C-004/5)
shares the Example Exchange B deposit address, C-006 ends in a mixer with no exchange,
C-007 is isolated (Example Exchange C), C-008 is still tracing past a bridge with idle funds.
"""
import hashlib
import json
import sys
from pathlib import Path

import base58

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from contract.schemas import CaseSummary, TraceResponse  # noqa: E402
from paths import FIXTURES, SEED_CASES, SEED_TRACES as OUT  # noqa: E402


# Same helpers as data/scripts/gen_fixtures.py (not imported: that script writes fixtures on import).
def tron(seed: str) -> str:
    raw = hashlib.sha256(seed.encode()).digest()[:20]
    return base58.b58encode_check(b"\x41" + raw).decode()


def evm(seed: str) -> str:
    return "0x" + hashlib.sha256(seed.encode()).hexdigest()[:40]


def txh(seed: str) -> str:
    return hashlib.sha256(("tx" + seed).encode()).hexdigest()


TYPOLOGY = {"investment": "investment_scam", "task": "task_scam", "sextortion": "sextortion",
            "ransomware": "ransomware", "phishing": "phishing"}

# Shared infrastructure (same addresses as the hero fixture where they overlap)
D_A, H_A = tron("hero-deposit-A"), tron("example-exchange-A-hot")
D_B, H_B = tron("NET-2-shared-deposit"), tron("example-exchange-B-hot")
D_C, H_C = tron("C-007-deposit-C"), tron("example-exchange-C-hot")
MX = tron("example-mixer")
BR_BSC = tron("example-bridge-bsc")

CONTACTS = {
    "Example Exchange A": "compliance@example-exchange-a.test",
    "Example Exchange B": "lea-requests@example-exchange-b.test",
    "Example Exchange C": "nodal.officer@example-exchange-c.test",
}


class Builder:
    """Collects nodes/edges for one case; times are offsets (seconds) from the first scam transfer."""

    def __init__(self, case: CaseSummary):
        self.c = case
        self.t0 = case.reported_at - 6 * 3600
        self.typ = TYPOLOGY.get(case.fraud_type, "unknown")
        self.nodes, self.edges = {}, []
        self.node(case.wallet, "scam_wallet", 0, "Reported", None, None,
                  self.scam_reasons(), self.typ)

    def scam_reasons(self):
        return {
            "investment": ["Many unrelated senders in a short window", "Forwards funds within minutes"],
            "task": ["Small repeated deposits from many victims", "Forwards funds within minutes"],
            "sextortion": ["Payments match extortion amounts", "New wallet, only inbound victim transfers"],
            "ransomware": ["Single large inbound payment", "Funds split and sent to a mixer"],
            "phishing": ["Received funds from drained victim wallet", "Wallet age under 2 days"],
        }.get(self.c.fraud_type, ["Reported in complaint"])

    def node(self, id, type, hop, label, risk="Low", score=0.05, reasons=(), typology="unknown",
             idle=0.0, chain="tron"):
        self.nodes[id] = dict(id=id, chain=chain, type=type, hop=hop, label=label, risk=risk,
                              risk_score=score, reasons=list(reasons), typology=typology,
                              idle_balance=idle)
        return id

    def victim(self, n):
        return self.node(tron(f"{self.c.case_id}-victim-{n}"), "victim", -1, "Victim wallet")

    def passthrough(self, n, hop=1, **kw):
        return self.node(tron(f"{self.c.case_id}-inter-{n}"), "intermediary", hop, "Pass-through wallet",
                         "High", 0.76, ["Forwards over 95% of received funds", "Wallet age under 5 days"],
                         self.typ, **kw)

    def tx(self, src, dst, amount, dt, edge_type="transfer"):
        self.edges.append(dict(source=src, target=dst, tx_hash=txh(f"{self.c.case_id}:{src}:{dst}"),
                               amount=amount, timestamp=self.t0 + dt, edge_type=edge_type))

    def build(self, nearest_vasp=None, notes=None) -> TraceResponse:
        nodes = list(self.nodes.values())
        return TraceResponse(
            case_id=self.c.case_id, complaint_id=self.c.complaint_id, wallet=self.c.wallet, chain="tron",
            fraud_type=self.c.fraud_type, amount_lost=self.c.amount_lost, risk=None,
            risk_score=None, typology=self.typ,
            graph={"nodes": nodes, "edges": self.edges},
            nearest_vasp=nearest_vasp,
            summary={
                "hops": max(n["hop"] for n in nodes),
                "nodes": len(nodes),
                "total_traced": sum(e["amount"] for e in self.edges if e["source"] == self.c.wallet),
                "idle_funds": sum(n["idle_balance"] for n in nodes),
                "time_to_attribution_sec": self.c.time_to_attribution_sec,
            },
            recommendations=[],  # filled by recommendations.py (B4) when the store loads
            source="simulated",
            generated_at=self.c.reported_at + 120,
            notes=notes or "FICTIONAL seed trace. Names and addresses are placeholders.",
        )

    # shared exchange legs
    def exchange_a(self, hop):
        self.node(D_A, "exchange", hop, "Example Exchange A (deposit address)", score=0.12,
                  reasons=["Behaves like an exchange deposit address"])
        self.node(H_A, "exchange", hop + 1, "Example Exchange A (hot wallet)",
                  reasons=["Labeled exchange hot wallet"])

    def exchange_b(self, hop):
        self.node(D_B, "exchange", hop, "Example Exchange B (deposit address)", score=0.1,
                  reasons=["Listed in Example Exchange B deposit-address set"])
        self.node(H_B, "exchange", hop + 1, "Example Exchange B (hot wallet)",
                  reasons=["Labeled exchange hot wallet"])

    def vasp(self, name, deposit, hops, amount, dt, confidence, method, evidence):
        return dict(vasp=name, deposit_address=deposit, hops=hops, amount=amount, timestamp=self.t0 + dt,
                    confidence=confidence, method=method, evidence=evidence, contact=CONTACTS[name])


SWEEP_A = [
    "Deposit address received funds from 14 unrelated wallets within 72 hours",
    "It forwarded 99% of its balance to a labeled hot wallet in a single transfer",
    f"Hot wallet {H_A[:8]}... is labeled Example Exchange A (source: demo label set)",
]
LISTED_B = [
    f"Deposit address {D_B[:8]}... appears in Example Exchange B's deposit-address set (demo label set)",
    f"Swept to labeled hot wallet {H_B[:8]}... within 30 minutes",
]


def c002(b: Builder):
    v1, v2 = b.victim(1), b.victim(2)
    s = b.c.wallet
    b.nodes[s]["idle_balance"] = 400.0
    i1 = b.passthrough(1)
    b.exchange_a(2)
    b.tx(v1, s, 2500.0, -5400)
    b.tx(v2, s, 2000.0, -3600)
    b.tx(s, i1, 4100.0, 0)
    b.tx(i1, D_A, 4080.0, 540)
    b.tx(D_A, H_A, 4070.0, 1800)
    return b.build(b.vasp("Example Exchange A", D_A, 2, 4080.0, 540, 0.84, "heuristic", SWEEP_A))


def c003(b: Builder):
    v1, v2 = b.victim(1), b.victim(2)
    s = b.c.wallet
    i1, i2 = b.passthrough(1), b.passthrough(2)
    b.exchange_a(2)
    b.tx(v1, s, 6000.0, -7200)
    b.tx(v2, s, 3800.0, -4000)
    b.tx(s, i1, 5200.0, 0)
    b.tx(s, i2, 4500.0, 90)
    b.tx(i1, D_A, 5180.0, 600)
    b.tx(i2, D_A, 4480.0, 780)
    b.tx(D_A, H_A, 9650.0, 2400)
    return b.build(b.vasp("Example Exchange A", D_A, 2, 9660.0, 780, 0.89, "heuristic", SWEEP_A))


def c004(b: Builder):
    v1 = b.victim(1)
    s = b.c.wallet
    b.exchange_b(1)
    b.tx(v1, s, 2200.0, -1800)
    b.tx(s, D_B, 2150.0, 0)
    b.tx(D_B, H_B, 2140.0, 1500)
    return b.build(b.vasp("Example Exchange B", D_B, 1, 2150.0, 0, 0.95, "deterministic", LISTED_B))


def c005(b: Builder):
    v1, v2 = b.victim(1), b.victim(2)
    s = b.c.wallet
    i1 = b.passthrough(1)
    b.exchange_b(2)
    b.tx(v1, s, 1000.0, -3000)
    b.tx(v2, s, 800.0, -2000)
    b.tx(s, i1, 1780.0, 0)
    b.tx(i1, D_B, 1770.0, 420)
    b.tx(D_B, H_B, 1765.0, 1600)
    return b.build(b.vasp("Example Exchange B", D_B, 2, 1770.0, 420, 0.95, "deterministic", LISTED_B))


def c006(b: Builder):
    v1 = b.victim(1)
    s = b.c.wallet
    i1, i2 = b.passthrough(1), b.passthrough(2)
    b.node(MX, "mixer", 2, "Example Mixer", "Critical", 0.91, ["Known mixing service"])
    b.tx(v1, s, 15500.0, -1200)
    b.tx(s, i1, 9000.0, 0)
    b.tx(s, i2, 6400.0, 45)
    b.tx(i1, MX, 9000.0, 300, "mixer_in")
    b.tx(i2, MX, 6400.0, 360, "mixer_in")
    return b.build(notes="FICTIONAL seed trace. Funds entered a mixer; no exchange reached.")


def c007(b: Builder):
    v1 = b.victim(1)
    s = b.c.wallet
    b.node(D_C, "exchange", 1, "Example Exchange C (deposit address)", score=0.1,
           reasons=["Behaves like an exchange deposit address"])
    b.node(H_C, "exchange", 2, "Example Exchange C (hot wallet)", reasons=["Labeled exchange hot wallet"])
    b.tx(v1, s, 3100.0, -900)
    b.tx(s, D_C, 3050.0, 0)
    b.tx(D_C, H_C, 3040.0, 2100)
    return b.build(b.vasp("Example Exchange C", D_C, 1, 3050.0, 0, 0.88, "heuristic", [
        "Deposit address received funds from 9 unrelated wallets within 48 hours",
        f"Swept its full balance to labeled hot wallet {H_C[:8]}... (Example Exchange C, demo label set)",
    ]))


def c008(b: Builder):
    v1, v2 = b.victim(1), b.victim(2)
    s = b.c.wallet
    i1 = b.passthrough(1)
    b.node(BR_BSC, "bridge", 2, "Example Bridge (TRON to BSC)", "Medium", 0.45, ["Cross-chain bridge contract"])
    e1 = b.node(evm("C-008-bsc-leg"), "intermediary", 3, "BSC-side wallet (funds still here)", "High", 0.72,
                ["Received bridged funds", "No outflow yet"], b.typ, idle=6250.0, chain="bsc")
    b.tx(v1, s, 4000.0, -4800)
    b.tx(v2, s, 2400.0, -2400)
    b.tx(s, i1, 6300.0, 0)
    b.tx(i1, BR_BSC, 6280.0, 360)
    b.tx(BR_BSC, e1, 6250.0, 900, "bridge")
    return b.build(notes="FICTIONAL seed trace. Trace still running on BSC past the bridge.")


BUILDERS = {"C-002": c002, "C-003": c003, "C-004": c004, "C-005": c005,
            "C-006": c006, "C-007": c007, "C-008": c008}


def main():
    cases = [CaseSummary(**c) for c in json.loads(SEED_CASES.read_text())]
    hero = TraceResponse(**json.loads((FIXTURES / "trace_hero.json").read_text()))
    traces = {}
    for c in cases:
        if c.case_id == "C-001":
            traces[c.case_id] = hero
        elif c.case_id in BUILDERS:
            traces[c.case_id] = BUILDERS[c.case_id](Builder(c))
        else:
            sys.exit(f"no seed trace builder for {c.case_id}")
    OUT.write_text(json.dumps({k: t.model_dump() for k, t in traces.items()}, indent=2))
    print(f"wrote {OUT.relative_to(ROOT)} ({len(traces)} traces)")


if __name__ == "__main__":
    main()
