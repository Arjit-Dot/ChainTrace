"""Person A: trace and wallet-risk endpoints. Replace the engine.py stub, not these signatures."""
from fastapi import APIRouter

import engine
from contract.schemas import TraceRequest, TraceResponse, WalletRisk

router = APIRouter()


@router.post("/api/trace", response_model=TraceResponse)
def trace(req: TraceRequest):
    return engine.trace_complaint(req)


@router.get("/api/wallets/{address}/risk", response_model=WalletRisk)
def risk(address: str):
    return engine.wallet_risk(address)
