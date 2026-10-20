"""
ChainTrace API (Person B owns the routes; Person A owns engine.py).

Run:  uvicorn main:app --reload --port 8000     (from the backend/ folder)
Docs: http://localhost:8000/docs
Every route works today on fixtures, so the frontend can be built immediately.
"""
import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

import engine_client
import store
from contract.schemas import (
    Alert, CaseSummary, DashboardStats, FreezeNotice, IntegrationAck, Network,
    SahyogNoticeRequest, TraceRequest, TraceResponse, WalletRisk, CONTRACT_VERSION,
)

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init()                            # seed cases + seed traces into the case store
    yield


app = FastAPI(title="ChainTrace API", version=CONTRACT_VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_alert_queues: List[asyncio.Queue] = []


@app.get("/api/health")
def health():
    return {"status": "ok", "contract_version": CONTRACT_VERSION, "engine_mode": engine_client.mode()}


# ---- Core ----
@app.post("/api/trace", response_model=TraceResponse)
def trace(req: TraceRequest):
    """Submit a complaint: run the engine, store the result as a new case, return it."""
    return store.add_case(req, engine_client.trace(req))  # TODO(B4): add recommendations


@app.get("/api/wallets/{address}/risk", response_model=WalletRisk)
def risk(address: str):
    return engine_client.risk(address)


# ---- Cases ----
@app.get("/api/cases", response_model=List[CaseSummary])
def list_cases():
    return store.list_cases()


@app.get("/api/cases/{case_id}", response_model=TraceResponse)
def get_case(case_id: str):
    trace = store.get_trace(case_id)
    if trace is None:
        raise HTTPException(404, "Case not found")
    return trace


@app.get("/api/cases/{case_id}/freeze-notice", response_model=FreezeNotice)
def freeze_notice(case_id: str):
    data = load("freeze_notice_hero.json")  # TODO(B): generate from the real case
    data["case_id"] = case_id
    return data


@app.get("/api/cases/{case_id}/report")
def report(case_id: str):
    return FileResponse(FIXTURES / "report_sample.pdf", media_type="application/pdf",
                        filename=f"{case_id}_evidence_report.pdf")  # TODO(B): real PDF


# ---- Analytics ----
@app.get("/api/dashboard", response_model=DashboardStats)
def dashboard():
    return load("dashboard.json")


@app.get("/api/networks", response_model=List[Network])
def networks():
    return load("networks.json")


# ---- Alerts (SSE) ----
@app.get("/api/alerts", response_model=List[Alert])
def alert_history():
    return load("alerts.json")


@app.get("/api/alerts/stream")
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


@app.post("/api/alerts/simulate", response_model=Alert)
async def simulate_alert():
    """Demo button: pushes the next fixture alert to every open stream."""
    alerts = load("alerts.json")
    alert = dict(alerts[int(time.time()) % len(alerts)])
    alert["timestamp"] = int(time.time())
    for q in list(_alert_queues):
        await q.put(alert)
    return alert


# ---- Mock integrations ----
@app.post("/api/integrations/ncrp/complaints", response_model=IntegrationAck)
def ncrp_complaint(req: TraceRequest):
    result = store.add_case(req, engine_client.trace(req))  # TODO(B6): publish alerts
    ack = load("ncrp_ack.json")
    ack.update(case_id=result.case_id, received_at=int(time.time()))
    return ack


@app.post("/api/integrations/sahyog/notice", response_model=IntegrationAck)
def sahyog_notice(req: SahyogNoticeRequest):
    ack = load("sahyog_ack.json")
    ack.update(case_id=req.case_id, received_at=int(time.time()))
    return ack
