"""
How the product side reaches the engine (Person B). Routes call this, never engine internals.

ENGINE_MODE
  fixture (default)  a pre-built trace: the seed trace for that wallet, else the hero trace
                     re-pointed at the reported wallet. Runs with no engine at all (Demo Mode).
  engine             the in-process seam, engine.trace_complaint / engine.wallet_risk.
  http               A's engine at ENGINE_URL (e.g. A's laptop before CP1).

If the engine or http call fails, the client falls back to the fixture so the demo never breaks;
the trace's `notes` say so.
"""
import json
import os
import time
from typing import Optional

import httpx

from contract.schemas import TraceRequest, TraceResponse, WalletRisk
from paths import FIXTURES, SEED_TRACES

MODES = ("fixture", "engine", "http")


def mode() -> str:
    m = os.getenv("ENGINE_MODE", "fixture").lower()
    return m if m in MODES else "fixture"


def _engine_url() -> str:
    return os.getenv("ENGINE_URL", "http://localhost:8001").rstrip("/")


def _seed_traces() -> dict:
    return json.loads(SEED_TRACES.read_text())


def _hero() -> dict:
    return json.loads((FIXTURES / "trace_hero.json").read_text())


# ---------- trace ----------
def trace(req: TraceRequest) -> TraceResponse:
    m = mode()
    if m == "fixture":
        return fixture_trace(req)
    try:
        if m == "engine":
            import engine  # the seam; imported lazily so fixture mode never loads engine code
            return engine.trace_complaint(req)
        r = httpx.post(f"{_engine_url()}/api/trace", json=req.model_dump(), timeout=60)
        r.raise_for_status()
        return TraceResponse(**r.json())
    except Exception as exc:  # demo must not break: fall back and say so
        return fixture_trace(req, note=f"Engine ({m}) unavailable: {exc}. Showing fixture data.")


def fixture_trace(req: TraceRequest, note: Optional[str] = None) -> TraceResponse:
    """The seed trace whose reported wallet matches, else the hero trace re-pointed at req.wallet."""
    data = next((t for t in _seed_traces().values() if t["wallet"] == req.wallet), None)
    if data is None:
        data = _repoint(_hero(), req.wallet, req.chain)
        note = " ".join(filter(None, [note, "Wallet not in the demo set: hero trace shown as an example."]))

    data.update(complaint_id=req.complaint_id, generated_at=int(time.time()), source="simulated")
    if req.amount is not None:
        data["amount_lost"] = req.amount
    if req.fraud_type:
        data["fraud_type"] = req.fraud_type
    if note:
        data["notes"] = " ".join(filter(None, [data.get("notes"), note]))
    return TraceResponse(**data)


def _repoint(data: dict, wallet: str, chain: Optional[str]) -> dict:
    """Rename the reported-wallet node (and its edges) so the graph starts at `wallet`."""
    old = data["wallet"]
    for n in data["graph"]["nodes"]:
        if n["id"] == old:
            n["id"] = wallet
            if chain:
                n["chain"] = chain
    for e in data["graph"]["edges"]:
        e["source"] = wallet if e["source"] == old else e["source"]
        e["target"] = wallet if e["target"] == old else e["target"]
    data["wallet"] = wallet
    if chain:
        data["chain"] = chain
    return data


# ---------- live monitoring ----------
def new_transfers(addresses: list, since_ts: int) -> list:
    """Outgoing transfers from `addresses` since `since_ts`. Only the in-process engine can see new transfers;
    fixture and http modes report none (an engine failure raises, so the watcher marks the case stale)."""
    if mode() != "engine":
        return []
    import engine
    return engine.new_transfers(addresses, since_ts)


def release_replay(address: str) -> int:
    """Demo: release a recorded movement for `address` (SIMULATED). 0 when there is none or not in engine mode."""
    if mode() != "engine":
        return 0
    import engine
    return engine.release_replay(address)


# ---------- wallet risk ----------
def risk(address: str) -> WalletRisk:
    m = mode()
    if m == "fixture":
        return fixture_risk(address)
    try:
        if m == "engine":
            import engine
            return engine.wallet_risk(address)
        r = httpx.get(f"{_engine_url()}/api/wallets/{address}/risk", timeout=30)
        r.raise_for_status()
        return WalletRisk(**r.json())
    except Exception:
        return fixture_risk(address)


def fixture_risk(address: str) -> WalletRisk:
    """Risk of a wallet as it appears in a seed trace, else the hero wallet's risk."""
    for t in _seed_traces().values():
        for n in t["graph"]["nodes"]:
            if n["id"] == address and n["risk"] is not None:  # the reported wallet is not scored in a trace
                return WalletRisk(address=address, risk=n["risk"], risk_score=n["risk_score"],
                                  reasons=n["reasons"], typology=n["typology"])
    data = json.loads((FIXTURES / "wallet_risk_hero.json").read_text())
    data["address"] = address
    return WalletRisk(**data)
