"""
ENGINE SEAM (Person A owns this file).

Right now both functions return fixtures, so the whole app runs end to end.
Replace the bodies with the real implementation (chain adapter -> tracing -> attribution -> risk).
Keep the signatures and return types exactly as they are; the API and UI depend on them.
"""
import json
import os
import time
from pathlib import Path

from contract.schemas import TraceRequest, TraceResponse, WalletRisk

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def trace_complaint(req: TraceRequest) -> TraceResponse:
    """Trace a reported wallet and return the full case.

    Step 4 is live: the graph comes from tracing.py (cache only unless TRONGRID_API_KEY is set).
    Step 5 attribution fills nearest_vasp; risk (A6) is still a placeholder.
    """
    if os.getenv("TRACING", "real") == "real":
        from chains.tron import TronAdapter
        from attribution import attribute
        from tracing import build_response, load_labels
        started = time.time()
        adapter = TronAdapter(offline=not os.getenv("TRONGRID_API_KEY"))
        resp = build_response(req, adapter)
        resp.nearest_vasp, resp.graph = attribute(resp.graph, adapter, load_labels())
        if resp.nearest_vasp:
            resp.summary.time_to_attribution_sec = round(time.time() - started, 2)
        else:
            resp.notes = "No exchange found in the traced flow."
        return resp
    data = _load("trace_hero.json")
    data["complaint_id"] = req.complaint_id
    data["wallet"] = req.wallet
    if req.amount is not None:
        data["amount_lost"] = req.amount
    if req.fraud_type:
        data["fraud_type"] = req.fraud_type
    data["generated_at"] = int(time.time())
    return TraceResponse(**data)


def wallet_risk(address: str) -> WalletRisk:
    """Risk level, score, reason codes and typology for one wallet. TODO(A): replace the stub."""
    data = _load("wallet_risk_hero.json")
    data["address"] = address
    return WalletRisk(**data)
