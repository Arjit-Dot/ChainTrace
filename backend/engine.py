"""
ENGINE SEAM (Person A owns this file).

Right now both functions return fixtures, so the whole app runs end to end.
Replace the bodies with the real implementation (chain adapter -> tracing -> attribution -> risk).
Keep the signatures and return types exactly as they are; the API and UI depend on them.

Besides trace_complaint and wallet_risk the seam has one light function for live monitoring:
new_transfers(addresses, since_ts). It lets the watcher poll a few wallets without a full re-trace.
release_replay() is the demo stand-in for live data: a recorded transfer (data/replay/movements.json)
is delivered once by new_transfers and then seen by the next trace. It is SIMULATED data.
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Set

from chains.tron import Transfer, TronAdapter, normalize
from contract.schemas import TraceRequest, TraceResponse, WalletRisk

DATA = Path(__file__).resolve().parents[1] / "data"
FIXTURES = DATA / "fixtures"
REPLAY = DATA / "replay" / "movements.json"

_released: Dict[str, List[Transfer]] = {}   # demo replay: transfers released so far, by sender
_pending: Set[str] = set()                  # released but not yet delivered by new_transfers


class _Adapter(TronAdapter):
    """The TRON adapter plus any released replay transfers."""

    def transfers(self, address, **kw):
        try:
            items, source = super().transfers(address, **kw)
        except LookupError:
            items, source = [], "cached"
        extra = [t for t in _released.values() for t in t if address in (t.from_addr, t.to_addr)]
        have = {t.tx_hash for t in items}
        items = sorted(items + [t for t in extra if t.tx_hash not in have], key=lambda t: (t.timestamp, t.tx_hash))
        if not items:
            raise LookupError(f"{address} is not cached and the adapter is offline")
        return items, source


def _adapter() -> TronAdapter:
    return _Adapter(offline=not os.getenv("TRONGRID_API_KEY"))


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def trace_complaint(req: TraceRequest) -> TraceResponse:
    """Trace a reported wallet and return the full case.

    Step 4 is live: the graph comes from tracing.py (cache only unless TRONGRID_API_KEY is set).
    Step 5 attribution fills nearest_vasp; risk (A6) is still a placeholder.
    """
    if os.getenv("TRACING", "real") == "real":
        from attribution import attribute
        from tracing import build_response, load_labels
        started = time.time()
        adapter = _adapter()
        resp = build_response(req, adapter)
        resp.nearest_vasp, resp.graph = attribute(resp.graph, adapter, load_labels())
        if resp.nearest_vasp:
            resp.summary.time_to_attribution_sec = round(time.time() - started, 2)
        else:
            resp.notes = "No exchange found in the traced flow."
        return resp
    data = _load("trace_hero.json")
    data["complaint_id"] = req.complaint_id
    data["wallet"] = req.wallet
    if req.amount is not None:
        data["amount_lost"] = req.amount
    if req.fraud_type:
        data["fraud_type"] = req.fraud_type
    data["generated_at"] = int(time.time())
    return TraceResponse(**data)


def wallet_risk(address: str) -> WalletRisk:
    """Risk level, score, reason codes and typology for one wallet. TODO(A): replace the stub."""
    data = _load("wallet_risk_hero.json")
    data["address"] = address
    return WalletRisk(**data)


def new_transfers(addresses: List[str], since_ts: int) -> List[Transfer]:
    """Outgoing transfers from `addresses` newer than `since_ts` (plus released replay transfers, once).

    Live with TRONGRID_API_KEY; otherwise reads the cache, so only the replay can produce news."""
    adapter = _adapter()
    live = bool(os.getenv("TRONGRID_API_KEY"))
    found: Dict[str, Transfer] = {}
    for addr in addresses:
        try:
            items, _ = adapter.transfers(addr, refresh=live)
        except (LookupError, ValueError):
            continue
        for t in items:
            if t.from_addr == addr and (t.timestamp > since_ts or t.tx_hash in _pending):
                found[t.tx_hash] = t
    _pending.difference_update(found)
    return sorted(found.values(), key=lambda t: (t.timestamp, t.tx_hash))


def release_replay(address: str) -> int:
    """Demo: release the recorded transfers sent by `address`. Returns how many were released (0 = none left)."""
    if not REPLAY.exists():
        return 0
    released = {t.tx_hash for ts in _released.values() for t in ts}
    fresh = [t for raw in json.loads(REPLAY.read_text()).get(address, []) if (t := normalize(raw))
             and t.tx_hash not in released]
    _released.setdefault(address, []).extend(fresh)
    _pending.update(t.tx_hash for t in fresh)
    return len(fresh)


def reset_replay() -> None:
    _released.clear()
    _pending.clear()
