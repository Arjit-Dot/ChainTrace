"""
Step 2 (Person A): pick 3 real, publicly flagged TRON wallets and cache their USDT history.

Source of "flagged": Tether's own USDT-TRC20 contract. Every `AddedBlackList` event is a
public, on-chain record that the issuer froze that address (typically after a law-enforcement
or fraud report). The script:
  1. reads recent AddedBlackList events from TronGrid,
  2. converts the event's hex address (`_user`) to a base58 T... address,
  3. keeps the first 3 wallets with a usable trace history (enough transfers, some outgoing),
  4. caches their raw transfer history via the Step 3 adapter (data/cache/tron/<addr>.json),
     saves each blacklist event (data/cache/blacklist_events/<addr>.json),
  5. also caches the biggest downstream recipients (one hop), so a trace works offline,
  6. writes data/cache/SOURCES.md.

Run from the repo root:   python data/scripts/scamWallet.py [--count 3] [--scan 50]
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from engine.chains.tron import USDT_TRC20, TronAdapter, hex_to_tron  # noqa: E402

CACHE = ROOT / "data" / "cache"
EVENTS_DIR = CACHE / "blacklist_events"
MIN_TRANSFERS, MIN_OUTGOING = 10, 3
NEXT_HOP = 3  # downstream recipients cached per wallet


def blacklist_events(adapter: TronAdapter, scan: int):
    body = adapter._get(f"/v1/contracts/{USDT_TRC20}/events",
                        {"event_name": "AddedBlackList", "limit": min(scan, 200),
                         "order_by": "block_timestamp,desc"})
    return body.get("data", [])


def utc(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.UTC).strftime("%Y-%m-%d %H:%M UTC")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--scan", type=int, default=50, help="how many recent blacklist events to consider")
    args = ap.parse_args()

    adapter = TronAdapter()
    picked = []
    for ev in blacklist_events(adapter, args.scan):
        user = (ev.get("result") or {}).get("_user")
        if not user:
            continue
        addr = hex_to_tron(user)
        if any(p["address"] == addr for p in picked):
            continue
        transfers, _ = adapter.transfers(addr, refresh=True)  # live, and written to the cache
        out = [t for t in transfers if t.from_addr == addr]
        print(f"{addr}: {len(transfers)} transfers, {len(out)} outgoing")
        if len(transfers) < MIN_TRANSFERS or len(out) < MIN_OUTGOING:
            adapter.cache_path(addr).unlink(missing_ok=True)  # not useful for the demo
            continue
        EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        (EVENTS_DIR / f"{addr}.json").write_text(json.dumps(ev, indent=2))
        picked.append({
            "address": addr, "event": ev, "transfers": transfers, "outgoing": len(out),
            "volume": sum(t.amount for t in transfers),
        })
        if len(picked) == args.count:
            break

    if len(picked) < args.count:
        sys.exit(f"only found {len(picked)} usable wallets; try a larger --scan")

    for p in picked:
        totals = {}
        for t in p["transfers"]:
            if t.from_addr == p["address"]:
                totals[t.to_addr] = totals.get(t.to_addr, 0.0) + t.amount
        p["next_hop"] = sorted(totals, key=totals.get, reverse=True)[:NEXT_HOP]
        for addr in p["next_hop"]:
            n = len(adapter.transfers(addr)[0])
            print(f"  next hop {addr}: {n} transfers cached")

    lines = [
        "# data/cache sources",
        "",
        "Every file in `data/cache/tron/` is a raw TronGrid response "
        "(`GET /v1/accounts/{address}/transactions/trc20?contract_address=" + USDT_TRC20 + "`), "
        "wrapped with `address`, `origin` and `fetched_at`.",
        "",
        "## Real wallets (live TronGrid data)",
        "",
        "Flagged = frozen by Tether on the USDT-TRC20 contract (`AddedBlackList` event). "
        "This is public and verifiable on-chain; Tether does not publish the reason for each freeze, "
        "so these are *flagged* wallets, not proven scam wallets. The raw event is saved in "
        "`blacklist_events/<address>.json`.",
        "",
        "| # | Address | Blacklisted | Blacklist tx | USDT transfers cached | Outgoing | Volume (USDT) | Next hop cached |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(picked, 1):
        ev = p["event"]
        lines.append(
            f"| {i} | `{p['address']}` | {utc(ev['block_timestamp'])} | "
            f"[{ev['transaction_id'][:12]}…](https://tronscan.org/#/transaction/{ev['transaction_id']}) | "
            f"{len(p['transfers'])} | {p['outgoing']} | {p['volume']:,.2f} | "
            + ", ".join(f"`{a[:8]}…`" for a in p["next_hop"]) + " |")
    lines += [
        "",
        f"Picked by `data/scripts/scamWallet.py` on {dt.datetime.now(dt.UTC):%Y-%m-%d}: the most recent blacklisted "
        f"wallets with at least {MIN_TRANSFERS} USDT transfers and {MIN_OUTGOING} outgoing (so there is something to trace). "
        f"The {NEXT_HOP} biggest recipients of each are cached too, so a 2-hop trace runs offline. "
        "Cached files of unlabeled addresses are *not* claims about their owners.",
        "",
        "## Scripted hero case (fictional)",
        "",
        "Files with `\"origin\": \"scripted-hero\"` are written by `data/scripts/make_hero_cache.py`. They are fictional "
        "(addresses derived from seed strings, the same as `data/fixtures/trace_hero.json`) and describe the agreed hero "
        "case C-001 in TronGrid format.",
        "",
    ]
    (CACHE / "SOURCES.md").write_text("\n".join(lines))
    print("wrote data/cache/SOURCES.md")


if __name__ == "__main__":
    main()
