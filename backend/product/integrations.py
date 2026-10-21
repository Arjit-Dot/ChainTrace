"""
Mock government integrations (Person B, B6). Both are SIMULATED stand-ins for the real systems.

NCRP  POST /api/integrations/ncrp/complaints  a complaint arrives from the portal: trace it, store the case,
                                              push NEW_COMPLAINT_LINKED / HIGH_RISK_WALLET alerts, acknowledge.
SAHYOG POST /api/integrations/sahyog/notice   the officer sends the freeze notice to the exchange: the case moves to
                                              notice_sent (the notice then reads "sent"), acknowledge.
"""
import asyncio
import time

from fastapi import APIRouter, HTTPException

from contract.schemas import IntegrationAck, SahyogNoticeRequest, TraceRequest
from product import alerts, engine_client, store

router = APIRouter(prefix="/api/integrations", tags=["integrations (simulated)"])


async def create_case(req: TraceRequest):
    """Trace, store, alert. Shared by the NCRP feed and the New Complaint form (/api/trace)."""
    def run():
        trace = store.add_case(req, engine_client.trace(req))  # store adds B's recommendations
        return trace, store.get_case(trace.case_id)

    trace, case = await asyncio.to_thread(run)
    for alert in alerts.on_new_case(trace, case):
        await alerts.publish(alert)
    return trace


@router.post("/ncrp/complaints", response_model=IntegrationAck)
async def ncrp_complaint(req: TraceRequest):
    trace = await create_case(req)
    now = int(time.time())
    return IntegrationAck(ack_id=f"NCRP-ACK-{trace.case_id}", status="queued", received_at=now, case_id=trace.case_id)


@router.post("/sahyog/notice", response_model=IntegrationAck)
def sahyog_notice(req: SahyogNoticeRequest):
    trace = store.get_trace(req.case_id)
    if trace is None:
        raise HTTPException(404, "Case not found")
    if trace.nearest_vasp is None:
        raise HTTPException(409, "No exchange identified for this case: nothing to send.")
    store.set_status(req.case_id, "notice_sent")
    now = int(time.time())
    return IntegrationAck(ack_id=f"SAH-ACK-{req.case_id}-{now}", status="received", received_at=now,
                          case_id=req.case_id)
