"""
ChainTrace API (Person B owns the routes; Person A owns the engine package).

Run:  uvicorn main:app --reload --port 8000     (from the backend/ folder)
Docs: http://localhost:8000/docs
Every route works today on fixtures, so the frontend can be built immediately.
"""
import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse

from paths import FIXTURES
from product import alerts, engine_client, store
from product.notices import build_freeze_notice
from product.reports import build_report, evidence_hash
from contract.schemas import (
    Alert, CaseSummary, DashboardStats, FreezeNotice, IntegrationAck, Network,
    SahyogNoticeRequest, TraceRequest, TraceResponse, WalletRisk, CONTRACT_VERSION,
)



def load(name: str):
    return json.loads((FIXTURES / name).read_text())


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init()                            # seed cases + seed traces into the case store
    watcher = asyncio.create_task(alerts.run_watcher()) if store.monitoring_on() else None
    yield
    if watcher:
        watcher.cancel()


app = FastAPI(title="ChainTrace API", version=CONTRACT_VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health():
    return {"status": "ok", "contract_version": CONTRACT_VERSION, "engine_mode": engine_client.mode()}


# ---- Core ----
@app.post("/api/trace", response_model=TraceResponse)
def trace(req: TraceRequest):
    """Submit a complaint: run the engine, store the result as a new case, return it."""
    return store.add_case(req, engine_client.trace(req))  # store adds B's recommendations


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
    """Draft the freeze notice from the stored trace. 404 when there is no exchange to freeze."""
    trace = store.get_trace(case_id)
    if trace is None:
        raise HTTPException(404, "Case not found")
    if trace.nearest_vasp is None:
        raise HTTPException(404, "No exchange identified for this case: nothing to freeze.")
    case = store.set_status(case_id, "notice_drafted", only_from={"attributed"})
    return build_freeze_notice(trace, case)


@app.get("/api/cases/{case_id}/report", response_class=Response,
         responses={200: {"content": {"application/pdf": {}}}})
def report(case_id: str):
    """PDF evidence report built from the stored trace. The footer hash is also sent as X-Evidence-SHA256."""
    trace = store.get_trace(case_id)
    if trace is None:
        raise HTTPException(404, "Case not found")
    pdf = build_report(trace, store.get_case(case_id))
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{case_id}_evidence_report.pdf"',
        "X-Evidence-SHA256": evidence_hash(trace),
    })


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
    return alerts.history()


@app.get("/api/alerts/stream")
async def alert_stream():
    q = alerts.subscribe()

    async def gen():
        try:
            while True:
                yield {"event": "alert", "data": json.dumps(await q.get())}
        finally:
            alerts.unsubscribe(q)

    return EventSourceResponse(gen())


@app.post("/api/alerts/simulate", response_model=Alert)
async def simulate_alert():
    """Demo button: pushes the next fixture alert to every open stream."""
    fixtures = load("alerts.json")
    alert = dict(fixtures[int(time.time()) % len(fixtures)])
    alert["timestamp"] = int(time.time())
    await alerts.publish(Alert(**alert))
    return alert


@app.post("/api/cases/{case_id}/simulate-movement", response_model=List[Alert])
async def simulate_movement(case_id: str):
    """Demo: replay a recorded movement of this case's idle funds (SIMULATED), re-check the case now, push alerts."""
    trace = store.get_trace(case_id)
    if trace is None:
        raise HTTPException(404, "Case not found")
    if not sum(engine_client.release_replay(a) for a in alerts.watchlist(trace)):
        raise HTTPException(404, "No recorded movement to replay for this case.")
    new = await asyncio.to_thread(alerts.poll_case, case_id, None, True)
    for alert in new:
        await alerts.publish(alert)
    return new


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
