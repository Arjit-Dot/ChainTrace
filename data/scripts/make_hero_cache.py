"""
Step 2 (Person A): script the hero case C-001 into data/cache/ in raw TronGrid format.

ALL DATA IS FICTIONAL. The transfers come straight from data/fixtures/trace_hero.json
(same addresses, tx hashes, amounts and times), so the real engine reproduces the fixture.
Added on top, so attribution has something to find:
  - the deposit address receives from 13 more unrelated wallets in the 72 hours before the
    hero deposit (14 senders in total) and sweeps each deposit to the labeled hot wallet;
  - the bridge exit (TRON -> Ethereum) goes to data/cache/bridge_legs.json, because the
    TRON adapter only sees the TRON side.

Run from the repo root:   python data/scripts/make_hero_cache.py
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from engine.chains.tron import USDT_TRC20, TronAdapter  # noqa: E402

FIXTURE = ROOT / "data" / "fixtures" / "trace_hero.json"
CACHE = ROOT / "data" / "cache"
TOKEN = {"symbol": "USDT", "address": USDT_TRC20, "decimals": 6, "name": "Tether USD"}
OTHER_DEPOSITORS = 13


def tron(seed: str) -> str:  # same scheme as data/scripts/gen_fixtures.py
    import base58
    raw = hashlib.sha256(seed.encode()).digest()[:20]
    return base58.b58encode_check(b"\x41" + raw).decode()


def txh(seed: str) -> str:
    return hashlib.sha256(("tx" + seed).encode()).hexdigest()


def raw_transfer(tx_hash, src, dst, amount, ts):
    return {"transaction_id": tx_hash, "token_info": TOKEN, "block_timestamp": ts * 1000,
            "from": src, "to": dst, "type": "Transfer", "value": str(round(amount * 10 ** 6))}


def main():
    hero = json.loads(FIXTURE.read_text())
    chain = {n["id"]: n["chain"] for n in hero["graph"]["nodes"]}
    deposit = hero["nearest_vasp"]["deposit_address"]
    hot = next(e["target"] for e in hero["graph"]["edges"] if e["source"] == deposit)

    transfers, bridge_legs = [], {}
    for e in hero["graph"]["edges"]:
        if chain[e["source"]] == "tron" and chain[e["target"]] == "tron":
            transfers.append(raw_transfer(e["tx_hash"], e["source"], e["target"], e["amount"], e["timestamp"]))
        else:  # bridge exit on the destination chain
            entry = next(x for x in hero["graph"]["edges"] if x["target"] == e["source"])
            bridge_legs[entry["tx_hash"]] = {
                "bridge": e["source"], "dest_chain": chain[e["target"]], "to": e["target"],
                "tx_hash": e["tx_hash"], "amount": e["amount"], "timestamp": e["timestamp"],
                "token": e["token"],
            }

    # Unrelated customers of the same deposit address, each swept to the hot wallet.
    hero_deposit_ts = hero["nearest_vasp"]["timestamp"]
    for i in range(1, OTHER_DEPOSITORS + 1):
        sender = tron(f"hero-depositor-{i}")
        amount = float(150 + (int(txh(f"amt{i}"), 16) % 4800))
        ts = hero_deposit_ts - i * 5 * 3600 - (i * 977) % 3600  # spread over ~70 hours
        transfers.append(raw_transfer(txh(f"dep{i}"), sender, deposit, amount, ts))
        transfers.append(raw_transfer(txh(f"sweep{i}"), deposit, hot, round(amount * 0.99, 2), ts + 900 + i * 60))

    by_addr = defaultdict(list)
    for t in transfers:
        by_addr[t["from"]].append(t)
        by_addr[t["to"]].append(t)

    adapter = TronAdapter(offline=True)
    for addr, items in by_addr.items():
        items.sort(key=lambda t: t["block_timestamp"], reverse=True)  # TronGrid order: newest first
        adapter.write_cache(addr, items, origin="scripted-hero")
    (CACHE / "bridge_legs.json").write_text(json.dumps(bridge_legs, indent=2))
    print(f"wrote {len(by_addr)} scripted cache files ({len(transfers)} transfers) and bridge_legs.json")


if __name__ == "__main__":
    main()
