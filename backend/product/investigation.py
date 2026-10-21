"""
Officer routes for the investigation ledger (Person B, stage 4.1).

  GET  /api/officer/cases/{case_id}/identifiers    everything known about who and what is involved
  POST /api/officer/cases/{case_id}/identifiers    add one by hand (for example from a phone call)
  GET  /api/officer/cases/{case_id}/leads          suggested next steps: which institution holds the identity, what to ask
"""
from typing import List

from fastapi import APIRouter, HTTPException

from contract.schemas import Identifier, IdentifierRequest, Lead
from product import ledger, store

router = APIRouter(prefix="/api/officer/cases", tags=["officer: investigation"])


def _require(case_id: str) -> None:
    if store.get_case(case_id) is None:
        raise HTTPException(404, "Case not found")


@router.get("/{case_id}/identifiers", response_model=List[Identifier])
def identifiers(case_id: str):
    _require(case_id)
    return store.list_identifiers(case_id)


@router.post("/{case_id}/identifiers", response_model=Identifier, status_code=201)
def add_identifier(case_id: str, req: IdentifierRequest):
    _require(case_id)
    try:
        added = ledger.add_by_officer(case_id, req)
    except ValueError as exc:
        raise HTTPException(422, f"Not a valid {req.kind.replace('_', ' ')}: {exc}")
    if added is None:
        raise HTTPException(409, "That is already in this case's ledger.")
    return added


@router.get("/{case_id}/leads", response_model=List[Lead])
def case_leads(case_id: str):
    _require(case_id)
    return ledger.leads(case_id)
