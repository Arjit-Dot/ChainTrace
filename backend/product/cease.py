"""
Report and cease (Person B, stage 5): the officer's last step on a case.

  1. REPORT  the evidence report (PDF) for the case, and the referral dossier (4.4)
  2. CEASE   a freeze, hold or takedown request for every endpoint that needs one: the exchange, the bank account, the
             token issuer for funds still sitting in a wallet, the platforms and domains behind the lure
  3. the complaint moves to "Action initiated" the moment the FIRST such request is sent (or the exchange notice is
     sent), and the citizen's tracker changes to the generic sentence for that stage. It says nothing about what was done.

Drafting is one click, but nothing is approved or sent for the officer: each draft goes through the same approval
workflow as every other request (outreach.py). Nothing is transmitted in the demo. Closing the open requests is a
separate, manual step: this module never closes one.
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from contract.schemas import CeaseItem, CeaseStatus, RequestCreate
from product import complaints, ledger, outreach, store

router = APIRouter(prefix="/api/officer/cases", tags=["officer: report and cease"])

CEASE_KINDS = ("freeze_request", "issuer_hold", "takedown_request")
SENT = ("sent", "acknowledged", "replied", "closed")
PRESERVE_FIRST = "Send the preservation notice first: a takedown can destroy the records."


def _complaint(case_id: str):
    return next((c for c in store.list_complaints() if c.case_id == case_id), None)


def plan(case_id: str) -> List[CeaseItem]:
    """Every freeze, hold or takedown the case's leads allow, with the request already drafted for it if there is one."""
    requests = {(r.lead_id, r.kind): r for r in store.list_requests(case_id)}
    out: List[CeaseItem] = []
    for lead in ledger.leads(case_id):
        ident = next((i for i in store.list_identifiers(case_id) if i.identifier_id == lead.identifier_id), None)
        for kind in CEASE_KINDS:
            if kind not in lead.requests:
                continue
            req = requests.get((lead.lead_id, kind))
            note = None
            if kind == "takedown_request" and "preservation_notice" in lead.requests:
                preserved = requests.get((lead.lead_id, "preservation_notice"))
                if preserved is None or preserved.status in ("draft", "approved"):
                    note = PRESERVE_FIRST
            out.append(CeaseItem(lead_id=lead.lead_id, choke_point=lead.choke_point, holder=lead.holder, kind=kind,
                                 subject=ident.value if ident else "", request_id=req.request_id if req else None,
                                 status=req.status if req else "not_drafted", note=note))
    return out


def status(case_id: str, drafted: int = 0) -> CeaseStatus:
    comp = _complaint(case_id)
    items = plan(case_id)
    case = store.get_case(case_id)
    return CeaseStatus(
        case_id=case_id, complaint_id=comp.complaint_id if comp else None, stage=comp.stage if comp else None,
        citizen_sees=complaints.MESSAGES[comp.stage] if comp else None, report_url=f"/api/cases/{case_id}/report", items=items,
        drafts_created=drafted, started=bool(case and case.status == "notice_sent") or any(i.status in SENT for i in items))


def initiate(case_id: str) -> CeaseStatus:
    """Draft every missing freeze/hold/takedown request (never approves or sends one). Safe to run again."""
    drafted = 0
    for item in plan(case_id):
        if item.request_id is None and outreach.create(case_id, RequestCreate(lead_id=item.lead_id, kind=item.kind)):
            drafted += 1
    return status(case_id, drafted)


def on_sent(case_id: str, what: str) -> None:
    """A freeze, hold or takedown was sent: the complaint moves to 'Action initiated' (only from 'investigating')."""
    comp = _complaint(case_id)
    if comp is not None and comp.stage == "investigating":
        complaints.advance_stage(comp, "action_initiated", f"{what} (SIMULATED: nothing is transmitted)")


@router.get("/{case_id}/cease", response_model=CeaseStatus)
def get_status(case_id: str):
    if store.get_trace(case_id) is None:
        raise HTTPException(404, "Case not found")
    return status(case_id)


@router.post("/{case_id}/cease", response_model=CeaseStatus)
def start(case_id: str):
    if store.get_trace(case_id) is None:
        raise HTTPException(404, "Case not found")
    return initiate(case_id)
