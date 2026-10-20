"""Person B: cases, reports, alerts, mock integrations. Serves fixtures until the TODO(B) stubs are replaced."""
import asyncio
import json
import time
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

import engine
from contract.schemas import (
    Alert, CaseSummary, DashboardStats, FreezeNotice, IntegrationAck, Network,
    SahyogNoticeRequest, TraceRequest, TraceResponse,
)

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"

router = APIRouter()
_alert_queues: List[asyncio.Queue] = []


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


# ---- Cases ----
@router.get("/api/cases", response_model=List[CaseSummary])
def list_cases():
    return load("cases.json")


@router.get("/api/cases/{case_id}", response_model=TraceResponse)
def get_case(case_id: str):
    cases = {c["case_id"]: c for c in load("cases.json")}
    if case_id not in cases:
        raise HTTPException(404, "Case not found")
    c = cases[case_id]
    data = load("trace_hero.json")          # TODO: serve the stored trace for this case
    data.update(case_id=c["case_id"], complaint_id=c["complaint_id"], wallet=c["wallet"],
                amount_lost=c["amount_lost"], fraud_type=c["fraud_type"])
    return data


@router.get("/api/cases/{case_id}/freeze-notice", response_model=FreezeNotice)
def freeze_notice(case_id: str):
    data = load("freeze_notice_hero.json")  # TODO(B): generate from the real case
    data["case_id"] = case_id
    return data


@router.get("/api/cases/{case_id}/report")
def report(case_id: str):
    return FileResponse(FIXTURES / "report_sample.pdf", media_type="application/pdf",
                        filename=f"{case_id}_evidence_report.pdf")  # TODO(B): real PDF


# ---- Analytics ----
@router.get("/api/dashboard", response_model=DashboardStats)
def dashboard():
    return load("dashboard.json")


@router.get("/api/networks", response_model=List[Network])
def networks():
    return load("networks.json")


# ---- Alerts (SSE) ----
@router.get("/api/alerts", response_model=List[Alert])
def alert_history():
    return load("alerts.json")


@router.get("/api/alerts/stream")
async def alert_stream():
    q: asyncio.Queue = asyncio.Queue()
    _alert_queues.append(q)

    async def gen():
        try:
            while True:
                alert = await q.get()
                yield {"event": "alert", "data": json.dumps(alert)}
        finally:
            _alert_queues.remove(q)

    return EventSourceResponse(gen())


@router.post("/api/alerts/simulate", response_model=Alert)
async def simulate_alert():
    """Demo button: pushes the next fixture alert to every open stream."""
    alerts = load("alerts.json")
    alert = dict(alerts[int(time.time()) % len(alerts)])
    alert["timestamp"] = int(time.time())
    for q in list(_alert_queues):
        await q.put(alert)
    return alert


# ---- Mock integrations ----
@router.post("/api/integrations/ncrp/complaints", response_model=IntegrationAck)
def ncrp_complaint(req: TraceRequest):
    result = engine.trace_complaint(req)    # real flow: queue a trace and return an ack
    ack = load("ncrp_ack.json")
    ack.update(case_id=result.case_id, received_at=int(time.time()))
    return ack


@router.post("/api/integrations/sahyog/notice", response_model=IntegrationAck)
def sahyog_notice(req: SahyogNoticeRequest):
    ack = load("sahyog_ack.json")
    ack.update(case_id=req.case_id, received_at=int(time.time()))
    return ack
