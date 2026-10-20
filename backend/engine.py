"""
ENGINE SEAM (Person A owns this file).

Right now both functions return fixtures, so the whole app runs end to end.
Replace the bodies with the real implementation (chain adapter -> tracing -> attribution -> risk).
Keep the signatures and return types exactly as they are; the API and UI depend on them.
"""
import json
import time
from pathlib import Path

from contract.schemas import TraceRequest, TraceResponse, WalletRisk

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def trace_complaint(req: TraceRequest) -> TraceResponse:
    """Trace a reported wallet and return the full case. TODO(A): replace the stub."""
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
