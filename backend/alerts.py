"""
Live monitoring and alerts (Person B, B6).

Once a case is traced, its leaf and idle wallets go on a watchlist and are polled (placeholder: every 30 s) through
engine_client.new_transfers. Every poll re-evaluates urgency and stamps the case "as of" now. When a wallet moved,
the case is re-traced (graph extended, attribution re-run), and alerts are pushed over SSE:
FUNDS_MOVED, REACHED_VASP, ENTERED_MIXER, and URGENCY_CHANGED (urgency can go down as well as up).

Demo mode: with no TronGrid key there is no live feed, so a recorded transaction replay stands in for it
(POST /api/cases/{id}/simulate-movement). Those results are SIMULATED, and the alert message says so.
"""
import asyncio
import json
import time
from pathlib import Path
from typing import List, Optional

import engine_client
import store
from contract.schemas import Alert, TraceRequest, TraceResponse
from recommendations import amount, describe

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
URGENCY_LABELS = {"act_now": "Act now", "act_soon": "Act soon", "preserve": "Preserve"}
LEAF_TYPES = {"scam_wallet", "intermediary", "unknown"}   # exchanges, bridges and mixers are endpoints, not watched

_queues: List[asyncio.Queue] = []
_live: List[Alert] = []          # alerts raised since startup, newest first
_counter = 0


# ---------- stream ----------
def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _queues.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _queues:
        _queues.remove(q)


def history() -> List[Alert]:
    return _live + [Alert(**a) for a in json.loads((FIXTURES / "alerts.json").read_text())]


async def publish(alert: Alert) -> None:
    for q in list(_queues):
        await q.put(alert.model_dump())


def _alert(type_: str, severity: str, case_id: str, message: str, now: float) -> Alert:
    global _counter
    _counter += 1
    alert = Alert(id=f"L-{_counter}", type=type_, severity=severity, case_id=case_id, message=message,
                  timestamp=int(now))
    _live.insert(0, alert)
    return alert


# ---------- watching ----------
def watchlist(trace: TraceResponse) -> List[str]:
    """Leaf wallets and any wallet still holding funds. Only these are polled, to stay inside API rate limits."""
    senders = {e.source for e in trace.graph.edges}
    return [n.id for n in trace.graph.nodes
            if n.hop >= 0 and n.type in LEAF_TYPES and (n.id not in senders or n.idle_balance > 0)]


def poll_case(case_id: str, now: Optional[float] = None, simulated: bool = False) -> List[Alert]:
    """One check of one case. A failed check changes nothing, so the case goes stale instead of looking fresh."""
    now = time.time() if now is None else now
    trace = store.get_trace(case_id)
    if trace is None:
        return []
    since = (trace.monitoring.last_checked_at if trace.monitoring else None) or trace.generated_at
    try:
        moved = engine_client.new_transfers(watchlist(trace), since)
        new_trace = None
        if moved:
            req = TraceRequest(complaint_id=trace.complaint_id, wallet=trace.wallet, amount=trace.amount_lost,
                               fraud_type=trace.fraud_type)
            new_trace = engine_client.trace(req)
            if "unavailable" in (new_trace.notes or ""):  # engine failed and fell back to a fixture: keep what we had
                return []
    except Exception:
        return []

    result = store.reevaluate(case_id, now, new_trace)
    if result is None:
        return []
    old, new = result
    alerts: List[Alert] = []
    if moved:
        by_id = {n.id: n for n in old.graph.nodes}
        src = describe(by_id[moved[0].from_addr]) if moved[0].from_addr in by_id else f"wallet {moved[0].from_addr[:8]}..."
        alerts.append(_alert("FUNDS_MOVED", "critical", case_id,
                             f"{amount(sum(t.amount for t in moved))} USDT moved out of {src}"
                             + (" (simulated replay)" if simulated else ""), now))
        if new.nearest_vasp and (old.nearest_vasp is None or old.nearest_vasp.vasp != new.nearest_vasp.vasp):
            alerts.append(_alert("REACHED_VASP", "warning", case_id,
                                 f"Funds reached {new.nearest_vasp.vasp} ({new.nearest_vasp.confidence:.0%} confidence)", now))
        if any(n.type == "mixer" for n in new.graph.nodes) and not any(n.type == "mixer" for n in old.graph.nodes):
            alerts.append(_alert("ENTERED_MIXER", "critical", case_id, "Funds entered a known mixer", now))
    if old.urgency != new.urgency:
        was, now_ = URGENCY_LABELS.get(old.urgency, "none"), URGENCY_LABELS[new.urgency]
        alerts.append(_alert("URGENCY_CHANGED", "warning", case_id,
                             f"Urgency changed from {was} to {now_}: {new.urgency_reasons[0]}", now))
    return alerts


def poll_all(now: Optional[float] = None) -> List[Alert]:
    return [a for cid in store.watched_cases() for a in poll_case(cid, now)]


async def run_watcher(interval: float = store.POLL_INTERVAL_SEC) -> None:
    """Background loop started with the app. The poll runs in a thread so the API stays responsive."""
    while True:
        await asyncio.sleep(interval)
        for alert in await asyncio.to_thread(poll_all):
            await publish(alert)
