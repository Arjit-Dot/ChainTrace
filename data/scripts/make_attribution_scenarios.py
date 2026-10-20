"""
Step 5 test scenarios: scripted (FICTIONAL) cases in raw TronGrid format, one per attribution outcome.

Writes the transfers to data/cache/tron/ (origin "scripted-scenario") and the wallet, amount and
expected result of each scenario to data/scenarios/scenarios.json. Paste a scenario's wallet into New Complaint
in the UI to see it, or run `pytest backend/tests/test_scenarios.py`.

Run from the repo root:   python data/scripts/make_attribution_scenarios.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "data" / "scripts"))
from engine.chains.tron import TronAdapter  # noqa: E402
from paths import REPLAY_JSON, SCENARIOS_JSON  # noqa: E402
from make_hero_cache import raw_transfer, tron, txh  # noqa: E402

BASE = 1_791_000_000   # in the past, so live monitoring never mistakes cached scenario transfers for new ones
EXCHANGE_A = "TJ4imTmNr3FZoqR2jsRBuXS2aNXNAsAXhK"   # labels.csv, all fictional
EXCHANGE_B = "TRtcU89W2N6MTT7DXvpzZUAvWQ8qPTAQhS"
EXCHANGE_C = "TQyp1x1VvbeSnvwt3bdCATtLTjm4wTE3SY"
MIXER = "TLhZTYvV5asB99Wz26sSandSaN1kZfFWbs"
BRIDGE = "TXzK7i61kT3ck6kZ3VeGZjUnPVwDS46sKM"


class Scenario:
    def __init__(self, key, title, amount, expect):
        self.key, self.title, self.amount, self.expect = key, title, amount, expect
        self.transfers, self.n = [], 0
        self.t = BASE + len(SCENARIOS) * 100_000
        self.wallet = self.w("scam")

    def w(self, name):
        return tron(f"{self.key}-{name}")

    def send(self, src, dst, amount, dt=300):
        self.n += 1
        self.t += dt
        self.transfers.append(raw_transfer(txh(f"{self.key}{self.n}"), src, dst, round(amount, 2), self.t))

    def customers(self, deposit, count, hot, share=1.0, other=None):
        """`count` unrelated customers pay `deposit`; it forwards `share` of each to `hot` (rest to `other`)."""
        for i in range(count):
            amt = float(200 + (int(txh(f"{self.key}c{i}"), 16) % 3000))
            self.send(self.w(f"cust{i}"), deposit, amt, dt=1800)
            self.send(deposit, hot, amt * share * 0.99, dt=600)
            if share < 1 and other:
                self.send(deposit, other, amt * (1 - share) * 0.99, dt=60)


SCENARIOS = []


def add(s):
    SCENARIOS.append(s)
    return s


# 1. funds go straight into a labeled hot wallet
s = Scenario("direct", "Direct match: scam -> intermediary -> Example Exchange C hot wallet", 8000,
             {"vasp": "Example Exchange C", "method": "deterministic", "deposit_address": EXCHANGE_C, "hops": 2})
p = s.w("p1")
s.send(s.w("victim"), s.wallet, 8000); s.send(s.wallet, p, 8000); s.send(p, EXCHANGE_C, 7920)
add(s)

# 2. classic deposit-address sweep, 9 senders
s = Scenario("sweep", "Sweep heuristic: deposit address with 9 senders sweeps to Example Exchange B", 5000,
             {"vasp": "Example Exchange B", "method": "heuristic", "hops": 2, "conf_min": 0.6, "conf_max": 0.89})
p, d = s.w("p1"), s.w("deposit")
s.send(s.w("victim"), s.wallet, 5000); s.send(s.wallet, p, 5000); s.send(p, d, 4950)
s.customers(d, 8, EXCHANGE_B); s.send(d, EXCHANGE_B, 4900)
s.expect["deposit_address"] = d
add(s)

# 3. decoy: busy address, but only half of it goes to the exchange
s = Scenario("decoy", "Decoy: 9-sender address forwards only ~50% to Example Exchange A, rest to an unknown wallet", 5000,
             {"vasp": "Example Exchange A", "method": "deterministic", "deposit_address": EXCHANGE_A})
p, d = s.w("p1"), s.w("deposit")
s.send(s.w("victim"), s.wallet, 5000); s.send(s.wallet, p, 5000); s.send(p, d, 4950)
s.customers(d, 8, EXCHANGE_A, share=0.5, other=s.w("elsewhere")); s.send(d, EXCHANGE_A, 2400); s.send(d, s.w("elsewhere"), 2400)
add(s)

# 4. too few senders for the heuristic: falls back to the labeled hot wallet
s = Scenario("quiet", "Quiet address: only 2 senders, so no sweep pattern; matches the hot wallet directly", 3000,
             {"vasp": "Example Exchange B", "method": "deterministic", "deposit_address": EXCHANGE_B})
p, d = s.w("p1"), s.w("deposit")
s.send(s.w("victim"), s.wallet, 3000); s.send(s.wallet, p, 3000); s.send(p, d, 2970)
s.send(d, EXCHANGE_B, 2940)
add(s)

# 5. nearest of two exchanges wins
s = Scenario("two-exchanges", "Two exchanges: split money, the nearer one (Example Exchange C, 2 hops) is named", 10000,
             {"vasp": "Example Exchange C", "method": "deterministic", "deposit_address": EXCHANGE_C, "hops": 2})
p1, p2, d = s.w("p1"), s.w("p2"), s.w("deposit")
s.send(s.w("victim"), s.wallet, 10000); s.send(s.wallet, p1, 5000); s.send(s.wallet, p2, 5000)
s.send(p2, EXCHANGE_C, 4950); s.send(p1, d, 4950); s.customers(d, 8, EXCHANGE_B)
add(s)

# 6. nothing found, money still sitting in a wallet
s = Scenario("idle", "No exchange: funds still idle in the last wallet (act now). Live-monitoring demo: the replay moves them to Example Exchange B", 6000, {"vasp": None, "idle": 5900.0})
p1, p2 = s.w("p1"), s.w("p2")
s.send(s.w("victim"), s.wallet, 6000); s.send(s.wallet, p1, 6000); s.send(p1, p2, 5900)
add(s)

REPLAY = {}   # recorded movements for the live-monitoring demo (SIMULATED), keyed by sender
REPLAY[p2] = [raw_transfer(txh("replay-idle"), p2, EXCHANGE_B, 5880.0, s.t + 600)]  # the idle funds finally move

# 7. mixer terminal
s = Scenario("mixer", "Mixer terminal: trace ends at a mixer, no exchange", 4000, {"vasp": None, "terminal": MIXER})
p = s.w("p1")
s.send(s.w("victim"), s.wallet, 4000); s.send(s.wallet, p, 4000); s.send(p, MIXER, 3950)
add(s)

# 8. bridge terminal
s = Scenario("bridge", "Bridge terminal: trace ends at a cross-chain bridge, no exchange", 4000, {"vasp": None, "terminal": BRIDGE})
p = s.w("p1")
s.send(s.w("victim"), s.wallet, 4000); s.send(s.wallet, p, 4000); s.send(p, BRIDGE, 3950)
add(s)


def main():
    by_addr = defaultdict(list)
    for sc in SCENARIOS:
        for t in sc.transfers:
            by_addr[t["from"]].append(t)
            by_addr[t["to"]].append(t)
    adapter = TronAdapter(offline=True)
    for addr, items in by_addr.items():
        items.sort(key=lambda t: t["block_timestamp"], reverse=True)
        adapter.write_cache(addr, items, origin="scripted-scenario")
    out = [{"key": sc.key, "title": sc.title, "wallet": sc.wallet, "amount": float(sc.amount), "expect": sc.expect}
           for sc in SCENARIOS]
    SCENARIOS_JSON.parent.mkdir(exist_ok=True)
    SCENARIOS_JSON.write_text(json.dumps(out, indent=2) + "\n")
    REPLAY_JSON.write_text(json.dumps(REPLAY, indent=2) + "\n")
    print(f"wrote {len(by_addr)} cache files, {SCENARIOS_JSON.relative_to(ROOT)} and {REPLAY_JSON.relative_to(ROOT)}")
    for o in out:
        print(f"{o['key']:<14} {o['wallet']}  {o['amount']:>8.0f}  {o['title']}")


if __name__ == "__main__":
    main()
