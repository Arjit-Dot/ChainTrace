"""
A7.4: find a REAL flow that ends at a labeled exchange, and cache it as a second end-to-end case.

  payer X --> reported wallet S0 --> deposit address D --> labeled exchange hot wallet H

H is a real labeled exchange wallet from data/reference/labels.csv. D is a real address that many different wallets
pay and that sweeps nearly all it receives to H (what an exchange deposit address looks like). S0 is one of D's payers
with a small, complete history. Everything is fetched live from TronGrid into a scratch cache; only the chosen
wallets are copied into data/cache/tron/, and the result is written to data/scenarios/real_case.json.

WHAT THIS IS NOT: S0 is not claimed to be a scam wallet (we cannot know), and the exchange label is not independently
verified (see data/reference/LABELS.md). It shows the engine reaching a real labeled exchange through real wallets.

Run from the repo root:   python data/scripts/make_real_case.py [--hot TDqSquXB...] [--max-calls 60]
Needs network. Works without a TronGrid key (about 1 request a second); a key in .env makes it faster.
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from engine.chains.tron import FetchError, TronAdapter  # noqa: E402
from engine.trace.attribution import sweep_stats  # noqa: E402
from engine.trace.tracing import load_labels  # noqa: E402
from paths import SCENARIOS, TRON_CACHE  # noqa: E402

DEFAULT_HOT = "TDqSquXBgUCLYvYC4XZgrprLK589dkhSCf"        # labeled Binance wallet in labels.csv
PAUSE = 1.1                                               # seconds between requests (no key: ~1 request a second)
MIN_PAYMENT = 500.0                                       # ignore tiny transfers
MAX_S0_TRANSFERS = 40                                     # the reported wallet should have a small, readable history


class Budget:
    def __init__(self, adapter: TronAdapter, max_calls: int):
        self.adapter, self.left, self.log = adapter, max_calls, []

    def fetch(self, addr: str):
        """(transfers, truncated) or None when the call budget or the network fails us."""
        if self.left <= 0:
            return None
        cached = self.adapter.cache_path(addr).exists()
        if not cached:
            self.left -= 1
            time.sleep(PAUSE)
        try:
            return self.adapter.transfers(addr)[0], self.adapter.history_truncated(addr)
        except FetchError as exc:
            print(f"  ! {addr[:8]}.. {exc.reason}")
            return None


def find_deposit_addresses(b: Budget, hot: str, labels, limit: int = 14):
    """Senders of `hot` that look like deposit addresses (many payers, nearly everything swept to `hot`)."""
    got = b.fetch(hot)
    if not got:
        return []
    inbound = [t for t in got[0] if t.to_addr == hot and t.amount >= MIN_PAYMENT and t.from_addr not in labels]
    seen, found = set(), []
    for t in reversed(inbound):                                   # newest first
        if t.from_addr in seen:
            continue
        seen.add(t.from_addr)
        if len(seen) > limit:
            break
        res = b.fetch(t.from_addr)
        if not res or res[1]:                                     # skip failures and truncated (partial) histories
            continue
        stats = sweep_stats(res[0], t.from_addr, hot, set())
        print(f"  candidate {t.from_addr[:8]}..: {len({x.from_addr for x in res[0] if x.to_addr == t.from_addr})} payers, "
              f"{'sweeps to hot wallet' if stats else 'not a sweep'}")
        if stats:
            found.append((t.from_addr, stats["senders"]))
    return sorted(found, key=lambda x: -x[1])


def find_payer(b: Budget, deposit: str, hot: str, labels, tries: int = 10):
    """A payer S0 of `deposit` with a small complete history that also has someone paying it (the 'victim')."""
    got = b.fetch(deposit)
    if not got:
        return None
    best = None
    seen = set()
    for t in reversed([x for x in got[0] if x.to_addr == deposit and x.amount >= MIN_PAYMENT]):
        s0 = t.from_addr
        if s0 in seen or s0 in labels or s0 in (hot, deposit):
            continue
        seen.add(s0)
        if len(seen) > tries:
            break
        res = b.fetch(s0)
        if not res or res[1] or len(res[0]) > MAX_S0_TRANSFERS:
            continue
        txs = res[0]
        payers = [x for x in txs if x.to_addr == s0 and x.timestamp <= t.timestamp and x.amount >= MIN_PAYMENT]
        sent = [x for x in txs if x.from_addr == s0]
        print(f"  payer {s0[:8]}..: {len(txs)} transfers, {len(payers)} inbound before paying D, sends to {len({x.to_addr for x in sent})} wallets")
        if payers and len({x.to_addr for x in sent}) <= 4:
            score = (len(txs), t.amount)
            if best is None or score < best[0]:
                best = (score, s0, t.amount, payers[-1].from_addr)
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hot", default=DEFAULT_HOT)
    ap.add_argument("--max-calls", type=int, default=60)
    args = ap.parse_args()
    labels = load_labels()
    if args.hot not in labels:
        sys.exit(f"{args.hot} is not a labeled address in labels.csv")
    scratch = Path(tempfile.mkdtemp(prefix="real_case_"))
    adapter = TronAdapter(cache_dir=scratch)
    b = Budget(adapter, args.max_calls)
    print(f"hot wallet {args.hot} = {labels[args.hot][0]}; scratch cache {scratch}")

    for deposit, payers in find_deposit_addresses(b, args.hot, labels):
        print(f"deposit address {deposit} ({payers} payers)")
        found = find_payer(b, deposit, args.hot, labels)
        if not found:
            continue
        _, s0, amount, victim = found
        wallets = {args.hot, deposit, s0, victim}
        for t in adapter.transfers(s0)[0]:                           # the reported wallet's other recipients
            if t.from_addr == s0:
                wallets.add(t.to_addr)
        for w in sorted(wallets - set(labels)):
            b.fetch(w)                                               # idle checks and the victim's side need these too
        TRON_CACHE.mkdir(parents=True, exist_ok=True)
        copied = []
        for w in wallets:
            src = adapter.cache_path(w)
            if src.exists():
                shutil.copy(src, TRON_CACHE / src.name)
                copied.append(w)
        SCENARIOS.mkdir(exist_ok=True)
        out = {"key": "real-exchange-flow", "wallet": s0, "amount": round(amount, 2), "hot_wallet": args.hot,
               "exchange": labels[args.hot][0], "deposit_address": deposit, "payer": victim, "cached_wallets": sorted(copied),
               "note": "REAL wallets. The exchange label is unverified (Dune) and the reported wallet is not claimed to be fraud.",
               "fetched_at": int(time.time())}
        (SCENARIOS / "real_case.json").write_text(json.dumps(out, indent=2) + "\n")
        print(f"\nDONE: reported wallet {s0}, amount {out['amount']}, {len(copied)} wallets cached, calls left {b.left}")
        shutil.rmtree(scratch, ignore_errors=True)
        return
    print("\nNo usable flow found within the call budget. Try --max-calls 120, another --hot, or add a TronGrid key.")
    shutil.rmtree(scratch, ignore_errors=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
