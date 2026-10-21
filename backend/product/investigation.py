"""
Officer routes for the investigation ledger (Person B, stage 4.1).

  GET  /api/officer/cases/{case_id}/identifiers    everything known about who and what is involved
  POST /api/officer/cases/{case_id}/identifiers    add one by hand (for example from a phone call)
  GET  /api/officer/cases/{case_id}/leads          suggested next steps: which institution holds the identity, what to ask
  GET  /api/officer/cases/{case_id}/outcomes       where the money went, and what each kind of endpoint needs
  GET  /api/officer/cases/{case_id}/mules          suspected mule wallets and accounts
"""
from typing import List

from fastapi import APIRouter, HTTPException

from contract.schemas import CasePeople, Identifier, IdentifierRequest, Lead, Mule, Outcome, PersonCluster
from product import ledger, outcomes, people, store

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


@router.get("/{case_id}/outcomes", response_model=List[Outcome])
def case_outcomes(case_id: str):
    _require(case_id)
    return outcomes.outcomes(case_id)


@router.get("/{case_id}/mules", response_model=List[Mule])
def case_mules(case_id: str):
    _require(case_id)
    return outcomes.mules(case_id)


@router.get("/{case_id}/people", response_model=CasePeople)
def case_people(case_id: str):
    """The linked cases (if any) and the people this case's own replies name. Inferences, never findings."""
    _require(case_id)
    return people.case_people(case_id)


clusters_router = APIRouter(prefix="/api/officer", tags=["officer: investigation"])


@clusters_router.get("/clusters", response_model=List[PersonCluster])
def all_clusters():
    return people.clusters()
