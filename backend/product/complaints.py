"""
Complaint intake and the officer inbox (Person B, portal stage 2).

CITIZEN (public)
  POST /api/complaints                    file a complaint: a complaint ID is issued, NOTHING is traced
  GET  /api/complaints/{id}/status        the coarse stage and generic messages, by complaint ID only

OFFICER
  GET  /api/officer/complaints[?stage=]   the inbox, newest first
  GET  /api/officer/complaints/{id}       one complaint in full
  POST /api/officer/complaints/{id}/review   received -> under review
  POST /api/officer/complaints/{id}/trace    trigger the trace: creates the case, stage -> investigating

What a citizen can learn is deliberately tiny (see ComplaintStatusView): the stage and a fixed sentence per stage.
Never the wallet, the amount, the exchange, the case, or how it is being handled. Complaint IDs are random (not
sequential) and the status lookup is rate limited, because the ID is the only thing protecting a complaint's status.
"""
import asyncio
import os
import secrets
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response

from contract.schemas import (Complaint, ComplaintEvent, ComplaintReceipt, ComplaintRequest, ComplaintStage,
                              ComplaintStatusView, ComplaintTimelineItem, TraceRequest)
from product import alerts, integrations, store

router = APIRouter(prefix="/api", tags=["complaints"])
officer = APIRouter(prefix="/api/officer", tags=["officer: complaints"])

STAGES = ("received", "under_review", "investigating", "action_initiated", "closed")
LABELS = {"received": "Received", "under_review": "Under review", "investigating": "Investigation in progress",
          "action_initiated": "Action initiated", "closed": "Closed"}
MESSAGES = {
    "received": "Your complaint has been registered.",
    "under_review": "An officer is reviewing your complaint.",
    "investigating": "Your complaint is being investigated.",
    "action_initiated": "Action has been initiated with the relevant institutions.",
    "closed": "Your complaint has been closed. For details, please call the National Cyber Crime Helpline 1930.",
}
NOT_FOUND = "No complaint was found for that ID. Check the ID and try again."

STATUS_LIMIT = int(os.getenv("CHAINTRACE_STATUS_LIMIT", "30"))      # lookups per minute per client (placeholder)
_lookups: Dict[str, Deque[float]] = defaultdict(deque)
_tracing: set = set()                                               # complaints whose trace is running right now


def new_complaint_id() -> str:
    """NCRP-<year>-<6 random digits>: random, so IDs cannot be guessed by counting."""
    year = time.gmtime().tm_year
    while True:
        cid = f"NCRP-{year}-{secrets.randbelow(10 ** 6):06d}"
        if store.get_complaint(cid) is None:
            return cid


def _event(stage: ComplaintStage, note: str, now: int) -> ComplaintEvent:
    return ComplaintEvent(at=now, stage=stage, note=note)


def create(req: ComplaintRequest, complaint_id: Optional[str] = None, source: str = "Citizen portal") -> Optional[Complaint]:
    """Store a new complaint in stage 'received'. None if the given complaint ID already exists."""
    now = int(time.time())
    rec = Complaint(complaint_id=complaint_id or new_complaint_id(), created_at=now, updated_at=now,
                    history=[_event("received", f"Complaint registered ({source})", now)],
                    **req.model_dump(exclude_none=False))
    return rec if store.add_complaint(rec) else None


def public_view(rec: Complaint) -> ComplaintStatusView:
    """The citizen's view. Built from the stage and the stage-change times ONLY: nothing else can leak into it."""
    seen, timeline = set(), []
    for e in rec.history:
        if e.stage not in seen:
            seen.add(e.stage)
            timeline.append(ComplaintTimelineItem(stage=e.stage, label=LABELS[e.stage], message=MESSAGES[e.stage], at=e.at))
    return ComplaintStatusView(complaint_id=rec.complaint_id, stage=rec.stage, label=LABELS[rec.stage],
                               message=MESSAGES[rec.stage], updated_at=rec.updated_at, timeline=timeline)


# ---------- citizen ----------
@router.post("/complaints", response_model=ComplaintReceipt, status_code=201)
async def file_complaint(req: ComplaintRequest):
    rec = create(req)
    await alerts.publish(alerts.complaint_received(rec.complaint_id, rec.state))
    return ComplaintReceipt(complaint_id=rec.complaint_id, stage=rec.stage, message=MESSAGES["received"])


@router.get("/complaints/{complaint_id}/status", response_model=ComplaintStatusView)
def complaint_status(complaint_id: str, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"          # a status must never be kept by a proxy or the browser history
    client = request.client.host if request.client else "unknown"
    window = _lookups[client]
    now = time.time()
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= STATUS_LIMIT:
        raise HTTPException(429, "Too many lookups. Please wait a minute and try again.")
    window.append(now)
    rec = store.get_complaint(complaint_id.strip())
    if rec is None:
        raise HTTPException(404, NOT_FOUND)
    return public_view(rec)


# ---------- officer ----------
def _get(complaint_id: str) -> Complaint:
    rec = store.get_complaint(complaint_id)
    if rec is None:
        raise HTTPException(404, "Complaint not found")
    return rec


@officer.get("/complaints", response_model=List[Complaint])
def inbox(stage: Optional[ComplaintStage] = Query(default=None)):
    return store.list_complaints(stage)


@officer.get("/complaints/{complaint_id}", response_model=Complaint)
def complaint_detail(complaint_id: str):
    return _get(complaint_id)


def _advance(rec: Complaint, stage: ComplaintStage, note: str, **extra) -> Complaint:
    now = int(time.time())
    return store.update_complaint(rec.complaint_id, stage=stage, updated_at=now, history=rec.history + [_event(stage, note, now)], **extra)


@officer.post("/complaints/{complaint_id}/review", response_model=Complaint)
def start_review(complaint_id: str):
    rec = _get(complaint_id)
    if rec.stage != "received":
        raise HTTPException(409, f"This complaint is already {LABELS[rec.stage].lower()}.")
    return _advance(rec, "under_review", "Opened for review by an officer")


@officer.post("/complaints/{complaint_id}/trace", response_model=Complaint)
async def trigger_trace(complaint_id: str):
    """Run the engine on the complaint's wallet, store the case, link it, and move the complaint to investigating."""
    rec = _get(complaint_id)
    if rec.case_id or rec.stage not in ("received", "under_review"):
        raise HTTPException(409, "A trace has already been run for this complaint.")
    if complaint_id in _tracing:
        raise HTTPException(409, "A trace is already running for this complaint.")
    _tracing.add(complaint_id)
    try:
        trace = await integrations.create_case(TraceRequest(
            complaint_id=rec.complaint_id, wallet=rec.wallet, chain=rec.chain, amount=rec.amount, currency=rec.currency,
            tx_hash=rec.tx_hash, fraud_type=rec.fraud_type, state=rec.state, reported_at=rec.created_at))
        return _advance(store.get_complaint(complaint_id), "investigating", f"Trace triggered: case {trace.case_id}", case_id=trace.case_id)
    finally:
        _tracing.discard(complaint_id)
