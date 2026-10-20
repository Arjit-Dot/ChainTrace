"""
TRON chain adapter (Person A, Step 3): fetch USDT-TRC20 transfers and normalize them.

- Cache first (data/cache/tron/<address>.json, raw TronGrid format), then live TronGrid,
  and live results are written back to the cache.
- Normalized to the contract's units: timestamps in Unix epoch SECONDS (UTC), amounts as
  token-unit floats (7850.0 = 7,850 USDT), never raw integers.
- detect_chain() routes addresses for every chain in the contract's Chain enum, even though
  only TRON is fully implemented.

CLI (refill the cache from live data):
    cd backend && python -m engine.chains.tron <address> [<address> ...] [--refresh] [--limit 200]
"""
import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional, Tuple

import base58
import httpx
from dotenv import load_dotenv

from paths import ROOT, TRON_CACHE

CACHE_DIR = TRON_CACHE
TRONGRID_URL = "https://api.trongrid.io"
USDT_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
PAGE_SIZE = 200  # TronGrid maximum

load_dotenv(ROOT / ".env")

FetchSource = Literal["cached", "live"]


@dataclass(frozen=True)
class Transfer:
    tx_hash: str
    from_addr: str
    to_addr: str
    amount: float          # token units
    timestamp: int         # Unix epoch seconds, UTC
    token: str = "USDT"


# ------------------------------------------------------------------ address detection
_B58 = r"[1-9A-HJ-NP-Za-km-z]"
_EVM = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BTC_LEGACY = re.compile(rf"^[13]{_B58}{{25,34}}$")
_BTC_BECH32 = re.compile(r"^(bc1)[02-9ac-hj-np-z]{11,71}$")
_SOLANA = re.compile(rf"^{_B58}{{32,44}}$")


def is_tron_address(address: str) -> bool:
    if not (isinstance(address, str) and len(address) == 34 and address.startswith("T")):
        return False
    try:
        raw = base58.b58decode_check(address)
    except ValueError:
        return False
    return len(raw) == 21 and raw[0] == 0x41


def detect_chain(address: str) -> Optional[str]:
    """Best-effort chain from address format. EVM addresses default to 'ethereum'
    (the same format is used on bsc / polygon; the caller can pass chain explicitly)."""
    a = (address or "").strip()
    if is_tron_address(a):
        return "tron"
    if _EVM.match(a):
        return "ethereum"
    if _BTC_BECH32.match(a.lower()):
        return "bitcoin"
    if _BTC_LEGACY.match(a):
        try:
            base58.b58decode_check(a)
            return "bitcoin"
        except ValueError:
            pass
    if _SOLANA.match(a):
        try:
            if len(base58.b58decode(a)) == 32:
                return "solana"
        except ValueError:
            pass
    return None


def hex_to_tron(hex_addr: str) -> str:
    """'0x<20 bytes>' or '41<20 bytes>' (as returned in TronGrid events) -> base58 'T...' address."""
    h = hex_addr[2:] if hex_addr.startswith("0x") else hex_addr
    if len(h) == 40:
        h = "41" + h
    return base58.b58encode_check(bytes.fromhex(h)).decode()


# ------------------------------------------------------------------ normalization
def normalize(raw: dict) -> Optional[Transfer]:
    """One raw TronGrid trc20 item -> Transfer. Non-USDT tokens and non-transfers are dropped."""
    info = raw.get("token_info") or {}
    if info.get("address") != USDT_TRC20 or raw.get("type", "Transfer") != "Transfer":
        return None
    decimals = int(info.get("decimals", 6))
    return Transfer(
        tx_hash=raw["transaction_id"],
        from_addr=raw["from"],
        to_addr=raw["to"],
        amount=int(raw["value"]) / 10 ** decimals,
        timestamp=int(raw["block_timestamp"]) // 1000,
        token=info.get("symbol", "USDT"),
    )


# ------------------------------------------------------------------ adapter
class TronAdapter:
    def __init__(self, api_key: Optional[str] = None, cache_dir: Path = CACHE_DIR,
                 client: Optional[httpx.Client] = None, offline: bool = False):
        self.api_key = api_key if api_key is not None else os.getenv("TRONGRID_API_KEY", "")
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        headers = {"TRON-PRO-API-KEY": self.api_key} if self.api_key else {}
        self.client = client or httpx.Client(base_url=TRONGRID_URL, headers=headers, timeout=20)

    # cache ---------------------------------------------------------
    def cache_path(self, address: str) -> Path:
        return self.cache_dir / f"{address}.json"

    def read_cache(self, address: str) -> Optional[dict]:
        p = self.cache_path(address)
        return json.loads(p.read_text()) if p.exists() else None

    def write_cache(self, address: str, raw: List[dict], origin: str = "trongrid") -> dict:
        doc = {"address": address, "chain": "tron", "origin": origin,
               "fetched_at": int(time.time()), "data": raw}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path(address).write_text(json.dumps(doc, indent=1))
        return doc

    # live ----------------------------------------------------------
    def fetch_live(self, address: str, limit: int = PAGE_SIZE) -> List[dict]:
        """Raw USDT-TRC20 transfers (newest first), following TronGrid's fingerprint paging."""
        params = {"contract_address": USDT_TRC20, "limit": min(limit, PAGE_SIZE)}
        out: List[dict] = []
        while len(out) < limit:
            body = self._get(f"/v1/accounts/{address}/transactions/trc20", params)
            out.extend(body.get("data", []))
            fingerprint = (body.get("meta") or {}).get("fingerprint")
            if not fingerprint or not body.get("data"):
                break
            params = {**params, "fingerprint": fingerprint}
        return out[:limit]

    def _get(self, path: str, params: dict, retries: int = 3) -> dict:
        for attempt in range(retries + 1):
            r = self.client.get(path, params=params)
            if r.status_code == 429 and attempt < retries:  # rate limited (no API key is ~1 req/s)
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            body = r.json()
            if body.get("success") is False:
                raise RuntimeError(f"TronGrid error for {path}: {body.get('error')}")
            return body
        raise RuntimeError("unreachable")

    # public --------------------------------------------------------
    def transfers(self, address: str, limit: int = PAGE_SIZE,
                  refresh: bool = False) -> Tuple[List[Transfer], FetchSource]:
        """All USDT transfers in or out of `address`, oldest first, plus where they came from."""
        if not is_tron_address(address):
            raise ValueError(f"not a TRON address: {address!r}")
        doc = None if refresh else self.read_cache(address)
        source: FetchSource = "cached"
        if doc is None:
            if self.offline:
                raise LookupError(f"{address} is not cached and the adapter is offline")
            doc = self.write_cache(address, self.fetch_live(address, limit))
            source = "live"
        items = [t for t in (normalize(r) for r in doc["data"]) if t]
        items.sort(key=lambda t: (t.timestamp, t.tx_hash))
        return items, source

    def outgoing(self, address: str, **kw) -> List[Transfer]:
        return [t for t in self.transfers(address, **kw)[0] if t.from_addr == address]

    def incoming(self, address: str, **kw) -> List[Transfer]:
        return [t for t in self.transfers(address, **kw)[0] if t.to_addr == address]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch USDT-TRC20 transfers into data/cache/tron/")
    ap.add_argument("addresses", nargs="+")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and fetch live")
    ap.add_argument("--limit", type=int, default=PAGE_SIZE)
    args = ap.parse_args(argv)
    adapter = TronAdapter()
    for a in args.addresses:
        items, source = adapter.transfers(a, limit=args.limit, refresh=args.refresh)
        print(f"{a}: {len(items)} USDT transfers ({source})")


if __name__ == "__main__":
    sys.exit(main())
