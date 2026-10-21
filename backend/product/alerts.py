"""
Live monitoring and alerts (Person B, B6).

Once a case is traced, its leaf and idle wallets go on a watchlist and are polled (placeholder: every 30 s) through
engine_client.new_transfers. Every poll re-evaluates urgency and stamps the case "as of" now. When a wallet moved,
the case is re-traced (graph extended, attribution re-run), and alerts are pushed over SSE:
FUNDS_MOVED, REACHED_VASP, ENTERED_MIXER, and URGENCY_CHANGED (urgency can go down as well as up).

Demo mode: with no TronGrid key there is no live feed, so a recorded transaction replay stands in for it
(POST /api/cases/{id}/simulate-movement). Those results are SIMULATED, and the alert message says so.
In fixture mode there is nothing to replay, so POST /api/alerts/simulate steps through a scripted, case-aware
sequence built from the stored trace instead (also marked simulated).

Routes: /api/alerts (history), /api/alerts/stream (SSE, event "alert"), /api/alerts/simulate.
"""
import asyncio
import json
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from contract.schemas import Alert, CaseSummary, TraceRequest, TraceResponse
from paths import FIXTURES
from product import engine_client, store
from product.recommendations import amount, describe
URGENCY_LABELS = {"act_now": "Act now", "act_soon": "Act soon", "preserve": "Preserve"}
LEAF_TYPES = {"scam_wallet", "intermediary", "unknown"}   # exchanges, bridges and mixers are endpoints, not watched

_queues: List[asyncio.Queue] = []
_live: List[Alert] = []          # alerts raised since startup, newest first
_counter = 0
_script_step: Dict[str, int] = {}   # next scripted step per case
SEVERITY = {"FUNDS_MOVED": "critical", "ENTERED_MIXER": "critical", "REACHED_VASP": "warning",
            "HIGH_RISK_WALLET": "warning", "URGENCY_CHANGED": "warning", "NEW_COMPLAINT_LINKED": "info"}
DEMO_CASE = "C-001"

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


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


# ---------- new cases (NCRP feed, New Complaint form) ----------
def _top_risk(trace: TraceResponse):
    """Riskiest suspect wallet downstream (labeled services like mixers and exchanges have their own alerts)."""
    scored = [n for n in trace.graph.nodes if n.hop > 0 and n.type in LEAF_TYPES and n.risk in ("High", "Critical")]
    return max(scored, key=lambda n: n.risk_score or 0, default=None)


def on_new_case(trace: TraceResponse, case: Optional[CaseSummary], now: Optional[float] = None) -> List[Alert]:
    """Alerts for a just-stored case: it joined a network, and/or its flow hits a high-risk wallet."""
    now = time.time() if now is None else now
    out: List[Alert] = []
    if case and case.network_id:
        linked = sum(c.network_id == case.network_id for c in store.list_cases())
        out.append(_alert("NEW_COMPLAINT_LINKED", "info", trace.case_id,
                          f"Complaint {trace.complaint_id} linked to {case.network_id} through a shared wallet "
                          f"({linked} complaints in the network)", now))
    top = _top_risk(trace)
    if top:
        out.append(_alert("HIGH_RISK_WALLET", "warning", trace.case_id,
                          f"Funds passed through {describe(top)}, scored {top.risk} ({top.risk_score:.2f})"
                          + (f": {top.reasons[0]}" if top.reasons else ""), now))
    return out


# ---------- scripted demo sequence ----------
def script(trace: TraceResponse, case: Optional[CaseSummary]) -> List[tuple]:
    """(type, message) steps for one case, in demo order, built from what its trace actually contains."""
    steps = []
    idle = sorted((n for n in trace.graph.nodes if n.idle_balance > 0), key=lambda n: -n.idle_balance)
    if idle:
        steps.append(("FUNDS_MOVED", f"{amount(idle[0].idle_balance)} USDT moved out of {describe(idle[0])}"))
    v = trace.nearest_vasp
    if v:
        steps.append(("REACHED_VASP", f"Funds reached {v.vasp} deposit address {v.deposit_address[:8]}... "
                                      f"({v.confidence:.0%} confidence)"))
    mixers = {n.id: n for n in trace.graph.nodes if n.type == "mixer"}
    if mixers:
        mixed = sum(e.amount for e in trace.graph.edges if e.target in mixers)
        steps.append(("ENTERED_MIXER", f"{amount(mixed)} USDT entered {describe(next(iter(mixers.values())))}; "
                                       f"trace-through is low confidence"))
    top = _top_risk(trace)
    if top:
        who = describe(top)
        steps.append(("HIGH_RISK_WALLET", f"{who[:1].upper()}{who[1:]} scored {top.risk} ({top.risk_score:.2f})"))
    if case and case.network_id:
        linked = sum(c.network_id == case.network_id for c in store.list_cases())
        steps.append(("NEW_COMPLAINT_LINKED", f"{linked} complaints now linked in {case.network_id}"))
    return steps


def next_scripted(case_id: str, now: Optional[float] = None) -> Optional[Alert]:
    """The case's next scripted step (wrapping round), or None when the case has nothing to show."""
    trace = store.get_trace(case_id)
    steps = script(trace, store.get_case(case_id)) if trace else []
    if not steps:
        return None
    i = _script_step.get(case_id, 0)
    _script_step[case_id] = (i + 1) % len(steps)
    type_, message = steps[i % len(steps)]
    return _alert(type_, SEVERITY[type_], case_id, f"{message} (simulated)", time.time() if now is None else now)


# ---------- routes ----------
@router.get("", response_model=List[Alert])
def alert_history():
    return history()


@router.get("/stream")
async def alert_stream():
    q = subscribe()

    async def gen():
        yield ServerSentEvent(comment="connected")  # first bytes now, so proxies open the stream straight away
        try:
            while True:
                yield {"event": "alert", "data": json.dumps(await q.get())}
        finally:
            unsubscribe(q)

    return EventSourceResponse(gen())


@router.post("/simulate", response_model=Alert)
async def simulate_alert(case_id: Optional[str] = None):
    """Demo button: push the next scripted alert for a case (default C-001) to every open stream. SIMULATED."""
    case_id = case_id or DEMO_CASE
    if store.get_trace(case_id) is None:
        raise HTTPException(404, "Case not found")
    alert = next_scripted(case_id)
    if alert is None:
        raise HTTPException(404, "Nothing to simulate for this case.")
    await publish(alert)
    return alert
