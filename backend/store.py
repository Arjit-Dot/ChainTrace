"""
Case store (Person B). SQLite file, one row per case: its CaseSummary and its full TraceResponse.

Seeded at startup from data/seed_cases.json + data/seed_traces.json. Seed rows are refreshed on
every start; cases created through /api/trace survive restarts until reset() (or deleting the
file). The engine stays stateless: it never touches this module.

CHAINTRACE_DB overrides the file path (tests use a temp file).
"""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

from contract.schemas import CaseSummary, TraceRequest, TraceResponse
from linking import case_groups
from recommendations import with_recommendations

DATA = Path(__file__).resolve().parents[1] / "data"
_lock = threading.Lock()


def _path() -> Path:
    return Path(os.getenv("CHAINTRACE_DB", DATA / "chaintrace.db"))


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_path())
    con.execute("""CREATE TABLE IF NOT EXISTS cases (
        case_id TEXT PRIMARY KEY,
        seq     INTEGER NOT NULL,
        summary TEXT NOT NULL,
        trace   TEXT NOT NULL)""")
    return con


def _seq(case_id: str) -> int:
    return int(case_id.split("-")[1])


# ---------- setup ----------
def init(reset: bool = False) -> None:
    """Create the table and (re)load the seed cases. reset=True also drops user-created cases."""
    cases = json.loads((DATA / "seed_cases.json").read_text())
    traces = json.loads((DATA / "seed_traces.json").read_text())
    networks = [c.get("network_id") for c in cases if c.get("network_id")]
    with _lock, _connect() as con:
        if reset:
            con.execute("DELETE FROM cases")
        for c in cases:
            summary = CaseSummary(**c)
            linked = networks.count(summary.network_id) - 1 if summary.network_id else 0
            trace = with_recommendations(TraceResponse(**traces[summary.case_id]), linked)
            summary = summary.model_copy(update={"urgency": trace.urgency, "urgency_reasons": trace.urgency_reasons})
            con.execute("INSERT OR REPLACE INTO cases VALUES (?, ?, ?, ?)",
                        (summary.case_id, _seq(summary.case_id),
                         summary.model_dump_json(), trace.model_dump_json()))


# ---------- reads ----------
def list_cases() -> List[CaseSummary]:
    """Newest first, so a just-submitted complaint sits at the top of the dashboard."""
    with _connect() as con:
        rows = con.execute("SELECT summary FROM cases").fetchall()
    cases = [CaseSummary.model_validate_json(r[0]) for r in rows]
    return sorted(cases, key=lambda c: (c.reported_at, _seq(c.case_id)), reverse=True)


def get_trace(case_id: str) -> Optional[TraceResponse]:
    with _connect() as con:
        row = con.execute("SELECT trace FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return TraceResponse.model_validate_json(row[0]) if row else None


def get_case(case_id: str) -> Optional[CaseSummary]:
    with _connect() as con:
        row = con.execute("SELECT summary FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return CaseSummary.model_validate_json(row[0]) if row else None


def all_traces() -> dict:
    with _connect() as con:
        rows = con.execute("SELECT case_id, trace FROM cases").fetchall()
    return {cid: TraceResponse.model_validate_json(t) for cid, t in rows}


# ---------- writes ----------
def add_case(req: TraceRequest, trace: TraceResponse) -> TraceResponse:
    """Store an engine result as a new case (next C-NNN id, B's recommendations added) and return it."""
    with _lock, _connect() as con:
        seq = (con.execute("SELECT MAX(seq) FROM cases").fetchone()[0] or 0) + 1
        case_id = f"C-{seq:03d}"
        trace = trace.model_copy(update={"case_id": case_id})
        network_id, linked = _network_for(con, case_id, trace)
        trace = with_recommendations(trace, linked)
        summary = CaseSummary(
            case_id=case_id,
            complaint_id=req.complaint_id,
            wallet=trace.wallet,
            amount_lost=req.amount if req.amount is not None else (trace.amount_lost or 0.0),
            fraud_type=req.fraud_type or trace.fraud_type or trace.typology.replace("_scam", ""),
            state=req.state or "Unknown",
            risk=trace.risk,
            urgency=trace.urgency,
            urgency_reasons=trace.urgency_reasons,
            status="attributed" if trace.nearest_vasp else "unresolved",
            vasp=trace.nearest_vasp.vasp if trace.nearest_vasp else None,
            time_to_attribution_sec=trace.summary.time_to_attribution_sec,
            network_id=network_id,
            reported_at=req.reported_at or int(time.time()),
        )
        con.execute("INSERT INTO cases VALUES (?, ?, ?, ?)",
                    (case_id, seq, summary.model_dump_json(), trace.model_dump_json()))
    return trace


def set_status(case_id: str, status: str, only_from: Optional[set] = None) -> Optional[CaseSummary]:
    """Move a case to `status` (optionally only if it is currently in `only_from`)."""
    with _lock, _connect() as con:
        row = con.execute("SELECT summary FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            return None
        summary = CaseSummary.model_validate_json(row[0])
        if only_from is None or summary.status in only_from:
            summary = summary.model_copy(update={"status": status})
            con.execute("UPDATE cases SET summary = ? WHERE case_id = ?", (summary.model_dump_json(), case_id))
    return summary


def _network_for(con: sqlite3.Connection, case_id: str, trace: TraceResponse) -> Tuple[Optional[str], int]:
    """(network id, number of other linked complaints). Join the network of any case sharing a scammer
    wallet; start a new one if none has an id yet."""
    rows = con.execute("SELECT case_id, summary, trace FROM cases").fetchall()
    traces = {cid: TraceResponse.model_validate_json(t) for cid, _, t in rows}
    nets = {cid: json.loads(s).get("network_id") for cid, s, _ in rows}
    traces[case_id] = trace
    group = next(g for g in case_groups(traces) if case_id in g)
    if len(group) == 1:
        return None, 0
    existing = sorted(n for cid in group if (n := nets.get(cid)))
    if existing:
        return existing[0], len(group) - 1
    used = [int(n.split("-")[1]) for n in nets.values() if n]
    net = f"NET-{max(used, default=0) + 1}"
    for cid in group - {case_id}:  # previously isolated cases join the new network too
        s = json.loads(next(s for c, s, _ in rows if c == cid))
        s["network_id"] = net
        con.execute("UPDATE cases SET summary = ? WHERE case_id = ?", (json.dumps(s), cid))
    return net, len(group) - 1
