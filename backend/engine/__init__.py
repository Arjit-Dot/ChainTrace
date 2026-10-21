"""
ENGINE SEAM (Person A owns this file).

Right now both functions return fixtures, so the whole app runs end to end.
Replace the bodies with the real implementation (chain adapter -> tracing -> attribution -> risk).
Keep the signatures and return types exactly as they are; the API and UI depend on them.

Besides trace_complaint and wallet_risk the seam has one light function for live monitoring:
new_transfers(addresses, since_ts). It lets the watcher poll a few wallets without a full re-trace.
release_replay() is the demo stand-in for live data: a recorded transfer (data/scenarios/replay_movements.json)
is delivered once by new_transfers and then seen by the next trace. It is SIMULATED data.
"""
import json
import os
import time
from typing import Dict, List, Optional, Set

from contract.schemas import TraceRequest, TraceResponse, WalletRisk
from engine.chains.tron import FetchError, Transfer, TronAdapter, is_tron_address, normalize, detect_chain
from paths import FIXTURES, REPLAY_JSON as REPLAY

_released: Dict[str, List[Transfer]] = {}   # demo replay: transfers released so far, by sender
_pending: Set[str] = set()                  # released but not yet delivered by new_transfers


class _Adapter(TronAdapter):
    """The TRON adapter plus any released replay transfers."""

    def transfers(self, address, **kw):
        failure = None
        try:
            items, source = super().transfers(address, **kw)
        except LookupError as exc:           # not cached (offline) or a failed live fetch: keep the reason
            items, source, failure = [], "cached", exc
        extra = [t for t in _released.values() for t in t if address in (t.from_addr, t.to_addr)]
        have = {t.tx_hash for t in items}
        items = sorted(items + [t for t in extra if t.tx_hash not in have], key=lambda t: (t.timestamp, t.tx_hash))
        if not items:
            raise failure or LookupError(f"{address} is not cached and the adapter is offline")
        return items, source


def _adapter() -> TronAdapter:
    return _Adapter(offline=not os.getenv("TRONGRID_API_KEY"))


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def trace_complaint(req: TraceRequest) -> TraceResponse:
    """Trace a reported wallet and return the full case.

    Step 4 is live: the graph comes from trace/tracing.py (cache only unless TRONGRID_API_KEY is set).
    Step 5 attribution fills nearest_vasp; Step 6 scores the downstream wallets and sets the case typology.
    """
    if os.getenv("TRACING", "real") == "real":
        from engine.model.risk import score_graph
        from engine.trace.attribution import attribute
        from engine.trace.tracing import TraceStats, build_response, load_labels
        started = time.time()
        adapter = _adapter()
        stats = TraceStats()
        resp = build_response(req, adapter, stats)
        resp.nearest_vasp, resp.graph = attribute(resp.graph, adapter, load_labels())
        resp.graph, resp.typology = score_graph(resp.graph, adapter, resp.wallet)
        if resp.nearest_vasp:
            resp.summary.time_to_attribution_sec = round(time.time() - started, 2)
        resp.notes = _notes(req.wallet, adapter, stats, resp)
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


def _notes(wallet: str, adapter, stats, resp: TraceResponse) -> Optional[str]:
    """What an officer should know about how complete this trace is (shown on the case)."""
    notes: List[str] = []
    if not is_tron_address(wallet):
        chain = detect_chain(wallet)
        notes.append(f"{chain.capitalize()} wallets are not traced yet: only TRON is." if chain
                     else "Not a valid wallet address: nothing to trace.")
    elif adapter.unavailable.get(wallet) == "not cached":
        notes.append("This wallet is not in the demo cache and no TronGrid key is set, so nothing could be traced. "
                     "Use a cached wallet, or set TRONGRID_API_KEY.")
    failed = {a: r for a, r in adapter.unavailable.items() if r != "not cached"}
    if failed:
        why = ", ".join(sorted(set(failed.values())))
        notes.append(f"{len(failed)} wallet(s) could not be fetched ({why}); the trace may be incomplete.")
    if stats.stopped:
        notes.append(f"Trace stopped at the {stats.stopped} after reading {stats.expanded} wallets; "
                     "smaller flows beyond that were not followed.")
    if stats.unchecked_leaves:
        notes.append(f"Idle balances were not checked for {stats.unchecked_leaves} wallet(s) (time ran out).")
    if not resp.nearest_vasp and not notes:
        notes.append("No exchange found in the traced flow.")
    return " ".join(notes) or None


def wallet_risk(address: str) -> WalletRisk:
    """Risk level, score, reason codes and typology for one wallet, from its own transfers (see model/risk.py).

    TRACING=fixture returns the hero fixture instead, like trace_complaint."""
    if os.getenv("TRACING", "real") != "real":
        data = _load("wallet_risk_hero.json")
        data["address"] = address
        return WalletRisk(**data)
    from engine.model.risk import wallet_risk_for
    from engine.trace.attribution import deposit_addresses
    from engine.trace.tracing import load_labels
    risk, score, reasons, typology = wallet_risk_for(address, _adapter(), load_labels(), deposit_addresses())
    return WalletRisk(address=address, risk=risk, risk_score=score, reasons=reasons, typology=typology)


def new_transfers(addresses: List[str], since_ts: int) -> List[Transfer]:
    """Outgoing transfers from `addresses` newer than `since_ts` (plus released replay transfers, once).

    Live with TRONGRID_API_KEY; otherwise reads the cache, so only the replay can produce news."""
    adapter = _adapter()
    live = bool(os.getenv("TRONGRID_API_KEY"))
    found: Dict[str, Transfer] = {}
    for addr in addresses:
        try:
            items, _ = adapter.transfers(addr, refresh=live)
        except FetchError:
            raise                                 # a failed check must not look like "nothing moved": the case goes stale
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
