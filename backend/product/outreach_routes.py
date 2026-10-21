"""Officer routes for requests and replies (investigation 4.3)."""
from typing import List

from fastapi import APIRouter, HTTPException

from contract.schemas import InstitutionRequest, Reply, RequestCreate
from product import alerts, outreach, store

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
