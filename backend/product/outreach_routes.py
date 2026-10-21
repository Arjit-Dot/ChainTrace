"""Officer routes for requests and replies (investigation 4.3)."""
from typing import List

import time

from fastapi import APIRouter, HTTPException, Query, Response

from contract.schemas import InstitutionRequest, Referral, ReferralRequest, Reply, RequestCreate
from product import alerts, dossier, outreach, store

router = APIRouter(prefix="/api/officer", tags=["officer: requests"])


def _case(case_id: str) -> None:
    if store.get_case(case_id) is None:
        raise HTTPException(404, "Case not found")


def _req(request_id: str) -> InstitutionRequest:
    req = store.get_request(request_id)
    if req is None:
        raise HTTPException(404, "Request not found")
    return req


@router.get("/cases/{case_id}/requests", response_model=List[InstitutionRequest])
def list_requests(case_id: str):
    _case(case_id)
    return store.list_requests(case_id)


@router.post("/cases/{case_id}/requests", response_model=InstitutionRequest, status_code=201)
def draft_request(case_id: str, body: RequestCreate):
    _case(case_id)
    try:
        req = outreach.create(case_id, body)
    except outreach.Refused as exc:
        raise HTTPException(422, str(exc))
    if req is None:
        raise HTTPException(409, "A request of this kind already exists for this lead.")
    return req


@router.get("/requests/{request_id}", response_model=InstitutionRequest)
def get_request(request_id: str):
    return _req(request_id)


def _move(request_id: str, to: str) -> InstitutionRequest:
    _req(request_id)
    try:
        return outreach.advance(request_id, to)
    except outreach.Refused as exc:
        raise HTTPException(409, str(exc))


@router.post("/requests/{request_id}/approve", response_model=InstitutionRequest)
def approve(request_id: str):
    return _move(request_id, "approved")


@router.post("/requests/{request_id}/send", response_model=InstitutionRequest)
def send(request_id: str):
    return _move(request_id, "sent")


@router.post("/requests/{request_id}/close", response_model=InstitutionRequest)
def close(request_id: str):
    _req(request_id)
    try:
        return outreach.close(request_id)
    except outreach.Refused as exc:
        raise HTTPException(409, str(exc))


@router.post("/requests/{request_id}/simulate", response_model=InstitutionRequest)
async def simulate(request_id: str):
    """Demo: the institution acknowledges, then replies (fictional). A reply adds identifiers and raises an alert."""
    _req(request_id)
    try:
        req, reply = outreach.simulate_step(request_id)
    except outreach.Refused as exc:
        raise HTTPException(409, str(exc))
    if reply:
        await alerts.publish(alerts.reply_received(req, len(reply.new_identifier_ids)))
    return req


@router.get("/requests/{request_id}/reply", response_model=Reply)
def get_reply(request_id: str):
    _req(request_id)
    reply = store.get_reply(request_id)
    if reply is None:
        raise HTTPException(404, "No reply yet")
    return reply


@router.post("/cases/{case_id}/demo-run")
def demo_run(case_id: str, rounds: int = Query(default=1, ge=1, le=outreach.MAX_ROUNDS)):
    """DEMO: draft, approve, send and simulate replies for every lead at once (SIMULATED, fictional)."""
    _case(case_id)
    return outreach.demo_run(case_id, rounds)


@router.get("/cases/{case_id}/dossier")
def get_dossier(case_id: str):
    """The referral dossier as a PDF. It says what is a record, what is an inference and what is missing."""
    _case(case_id)
    pdf = dossier.build(case_id)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{case_id}_referral_dossier.pdf"', "Cache-Control": "no-store"})


@router.get("/cases/{case_id}/referral", response_model=Referral)
def get_referral(case_id: str):
    _case(case_id)
    ref = store.get_referral(case_id)
    if ref is None:
        raise HTTPException(404, "This case has not been referred.")
    return ref


@router.post("/cases/{case_id}/referral", response_model=Referral, status_code=201)
def refer(case_id: str, body: ReferralRequest):
    """An officer records that the case was referred to an investigating agency, with the hash of the dossier as it stood."""
    _case(case_id)
    rec = Referral(case_id=case_id, agency=body.agency.strip(), note=body.note, referred_at=int(time.time()),
                   dossier_sha256=dossier.dossier_hash(dossier.data(case_id)))
    if not store.add_referral(rec):
        raise HTTPException(409, "This case has already been referred.")
    return rec
