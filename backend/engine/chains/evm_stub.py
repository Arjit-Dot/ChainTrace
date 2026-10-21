"""
A stand-in for a second chain (Step A7.5): seeded transfers for Ethereum-side wallets, so a trace can follow money
across a bridge. SIMULATED: nothing here is fetched from a real chain, and it reads files only (no network).

data/cache/evm/<address, lowercase>.json:
    {"address": ..., "chain": "ethereum", "origin": "scripted-evm",
     "data": [{"tx_hash", "from", "to", "amount" (token units), "timestamp" (epoch seconds), "token"}]}
"""
import json
from pathlib import Path
from typing import List, Tuple

from engine.chains.tron import Transfer
from paths import EVM_CACHE


class EvmStubAdapter:
    offline = True

    def __init__(self, cache_dir: Path = EVM_CACHE):
        self.cache_dir = Path(cache_dir)
        self.unavailable: dict = {}

    def path(self, address: str) -> Path:
        return self.cache_dir / f"{address.lower()}.json"

    def transfers(self, address: str) -> Tuple[List[Transfer], str]:
        p = self.path(address)
        if not p.exists():
            self.unavailable[address] = "not seeded"
            raise LookupError(f"{address} has no seeded transfers")
        doc = json.loads(p.read_text())
        items = [Transfer(tx_hash=r["tx_hash"], from_addr=r["from"].lower(), to_addr=r["to"].lower(),
                          amount=float(r["amount"]), timestamp=int(r["timestamp"]), token=r.get("token", "USDT"))
                 for r in doc["data"]]
        return sorted(items, key=lambda t: (t.timestamp, t.tx_hash)), "cached"
