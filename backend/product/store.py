"""
Case store (Person B). SQLite file, one row per case: its CaseSummary and its full TraceResponse.

Seeded at startup from data/seed/seed_cases.json + data/seed/seed_traces.json. Seed rows are refreshed on
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

from contract.schemas import (CaseSummary, Complaint, Identifier, InstitutionRequest, Monitoring, Reply, TraceRequest,
                              TraceResponse)
from paths import DATA, SEED_CASES, SEED_COMPLAINTS, SEED_TRACES
from product.linking import case_groups
from product.recommendations import with_recommendations

POLL_INTERVAL_SEC = float(os.getenv("CHAINTRACE_POLL_SEC", "30"))   # placeholder, to be tuned by investigators
STALE_AFTER = 2                                                   # stale = last check older than 2 poll intervals
_lock = threading.Lock()


def monitoring_on() -> bool:
    return os.getenv("CHAINTRACE_MONITOR", "1") != "0"


def _monitoring(now: float) -> Monitoring:
    """The monitoring block stamped on a case that was just checked (status 'off' when the watcher is disabled)."""
    return Monitoring(status="live" if monitoring_on() else "off", last_checked_at=int(now),
                      poll_interval_sec=POLL_INTERVAL_SEC)


def _aged(obj, now: Optional[float] = None):
    """Stale is derived at read time: a live case whose last check is older than 2 poll intervals."""
    m = obj.monitoring
    if m is None or m.status != "live" or m.last_checked_at is None:
        return obj
    now = time.time() if now is None else now
    if now - m.last_checked_at > STALE_AFTER * m.poll_interval_sec:
        return obj.model_copy(update={"monitoring": m.model_copy(update={"status": "stale"})})
    return obj


def _path() -> Path:
    return Path(os.getenv("CHAINTRACE_DB", DATA / "chaintrace.db"))


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_path())
    con.execute("""CREATE TABLE IF NOT EXISTS cases (
        case_id TEXT PRIMARY KEY,
        seq     INTEGER NOT NULL,
        summary TEXT NOT NULL,
        trace   TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS identifiers (
        identifier_id TEXT PRIMARY KEY,
        case_id       TEXT NOT NULL,
        kind          TEXT NOT NULL,
        value         TEXT NOT NULL,
        record        TEXT NOT NULL,
        UNIQUE (case_id, kind, value))""")
    con.execute("""CREATE TABLE IF NOT EXISTS requests (
        request_id TEXT PRIMARY KEY,
        case_id    TEXT NOT NULL,
        lead_id    TEXT NOT NULL,
        kind       TEXT NOT NULL,
        record     TEXT NOT NULL,
        UNIQUE (case_id, lead_id, kind))""")
    con.execute("""CREATE TABLE IF NOT EXISTS replies (
        reply_id   TEXT PRIMARY KEY,
        request_id TEXT NOT NULL UNIQUE,
        case_id    TEXT NOT NULL,
        record     TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS complaints (
        complaint_id TEXT PRIMARY KEY,
        created_at   INTEGER NOT NULL,
        record       TEXT NOT NULL)""")
    return con


def _seq(case_id: str) -> int:
    return int(case_id.split("-")[1])


# ---------- setup ----------
def init(reset: bool = False) -> None:
    """Create the table and (re)load the seed cases. reset=True also drops user-created cases."""
    cases = json.loads(SEED_CASES.read_text())
    traces = json.loads(SEED_TRACES.read_text())
    networks = [c.get("network_id") for c in cases if c.get("network_id")]
    with _lock, _connect() as con:
        if reset:
            con.execute("DELETE FROM cases")
            con.execute("DELETE FROM complaints")
            con.execute("DELETE FROM identifiers")
            con.execute("DELETE FROM requests")
            con.execute("DELETE FROM replies")
        for c in cases:
            summary = CaseSummary(**c)
            linked = networks.count(summary.network_id) - 1 if summary.network_id else 0
            now = time.time()
            trace = with_recommendations(TraceResponse(**traces[summary.case_id]), linked, now)
            trace = trace.model_copy(update={"urgency_as_of": int(now), "monitoring": _monitoring(now)})
            summary = summary.model_copy(update={"urgency": trace.urgency, "urgency_reasons": trace.urgency_reasons,
                                                 "urgency_as_of": trace.urgency_as_of, "monitoring": trace.monitoring})
            con.execute("INSERT OR REPLACE INTO cases VALUES (?, ?, ?, ?)",
                        (summary.case_id, _seq(summary.case_id),
                         summary.model_dump_json(), trace.model_dump_json()))
        _seed_complaints(con)


# ---------- identifiers (the investigation ledger) ----------
def add_identifier(case_id: str, kind: str, value: str, make) -> Optional[Identifier]:
    """Insert an identifier built by make(n) (n = its number within the case). None if the case already has that kind+value."""
    with _lock, _connect() as con:
        if con.execute("SELECT 1 FROM identifiers WHERE case_id = ? AND kind = ? AND value = ?", (case_id, kind, value)).fetchone():
            return None
        n = con.execute("SELECT COUNT(*) FROM identifiers WHERE case_id = ?", (case_id,)).fetchone()[0] + 1
        rec = make(n)
        con.execute("INSERT INTO identifiers VALUES (?, ?, ?, ?, ?)", (rec.identifier_id, case_id, kind, value, rec.model_dump_json()))
        return rec


def list_identifiers(case_id: str) -> List[Identifier]:
    with _connect() as con:
        rows = con.execute("SELECT record FROM identifiers WHERE case_id = ? ORDER BY rowid", (case_id,)).fetchall()
    return [Identifier.model_validate_json(r[0]) for r in rows]


# ---------- requests to institutions and their replies ----------
def add_request(case_id: str, lead_id: str, kind: str, make) -> Optional[InstitutionRequest]:
    """Insert a request built by make(n). None if this lead already has a request of this kind."""
    with _lock, _connect() as con:
        if con.execute("SELECT 1 FROM requests WHERE case_id = ? AND lead_id = ? AND kind = ?", (case_id, lead_id, kind)).fetchone():
            return None
        n = con.execute("SELECT COUNT(*) FROM requests WHERE case_id = ?", (case_id,)).fetchone()[0] + 1
        rec = make(n)
        con.execute("INSERT INTO requests VALUES (?, ?, ?, ?, ?)", (rec.request_id, case_id, lead_id, kind, rec.model_dump_json()))
        return rec


def get_request(request_id: str) -> Optional[InstitutionRequest]:
    with _connect() as con:
        row = con.execute("SELECT record FROM requests WHERE request_id = ?", (request_id,)).fetchone()
    return InstitutionRequest.model_validate_json(row[0]) if row else None


def list_requests(case_id: str) -> List[InstitutionRequest]:
    with _connect() as con:
        rows = con.execute("SELECT record FROM requests WHERE case_id = ? ORDER BY rowid", (case_id,)).fetchall()
    return [InstitutionRequest.model_validate_json(r[0]) for r in rows]


def update_request(request_id: str, **changes) -> Optional[InstitutionRequest]:
    with _lock, _connect() as con:
        row = con.execute("SELECT record FROM requests WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            return None
        rec = InstitutionRequest.model_validate_json(row[0]).model_copy(update=changes)
        con.execute("UPDATE requests SET record = ? WHERE request_id = ?", (rec.model_dump_json(), request_id))
    return rec


def add_reply(rec: Reply) -> bool:
    with _lock, _connect() as con:
        cur = con.execute("INSERT OR IGNORE INTO replies VALUES (?, ?, ?, ?)", (rec.reply_id, rec.request_id, rec.case_id, rec.model_dump_json()))
        return cur.rowcount == 1


def get_reply(request_id: str) -> Optional[Reply]:
    with _connect() as con:
        row = con.execute("SELECT record FROM replies WHERE request_id = ?", (request_id,)).fetchone()
    return Reply.model_validate_json(row[0]) if row else None


def _seed_complaints(con: sqlite3.Connection) -> None:
    if not SEED_COMPLAINTS.exists():
        return
    for c in json.loads(SEED_COMPLAINTS.read_text()):
        rec = Complaint(**c)
        con.execute("INSERT OR IGNORE INTO complaints VALUES (?, ?, ?)", (rec.complaint_id, rec.created_at, rec.model_dump_json()))


# ---------- complaints (portal intake) ----------
def add_complaint(rec: Complaint) -> bool:
    """Store a new complaint. False if that complaint ID already exists."""
    with _lock, _connect() as con:
        cur = con.execute("INSERT OR IGNORE INTO complaints VALUES (?, ?, ?)", (rec.complaint_id, rec.created_at, rec.model_dump_json()))
        return cur.rowcount == 1


def get_complaint(complaint_id: str) -> Optional[Complaint]:
    with _connect() as con:
        row = con.execute("SELECT record FROM complaints WHERE complaint_id = ?", (complaint_id,)).fetchone()
    return Complaint.model_validate_json(row[0]) if row else None


def list_complaints(stage: Optional[str] = None) -> List[Complaint]:
    """Newest first."""
    with _connect() as con:
        rows = con.execute("SELECT record FROM complaints ORDER BY created_at DESC, complaint_id DESC").fetchall()
    out = [Complaint.model_validate_json(r[0]) for r in rows]
    return [c for c in out if stage is None or c.stage == stage]


def update_complaint(complaint_id: str, **changes) -> Optional[Complaint]:
    with _lock, _connect() as con:
        row = con.execute("SELECT record FROM complaints WHERE complaint_id = ?", (complaint_id,)).fetchone()
        if row is None:
            return None
        rec = Complaint.model_validate_json(row[0]).model_copy(update=changes)
        con.execute("UPDATE complaints SET record = ? WHERE complaint_id = ?", (rec.model_dump_json(), complaint_id))
    return rec


# ---------- reads ----------
def list_cases() -> List[CaseSummary]:
    """Newest first, so a just-submitted complaint sits at the top of the dashboard."""
    with _connect() as con:
        rows = con.execute("SELECT summary FROM cases").fetchall()
    cases = [_aged(CaseSummary.model_validate_json(r[0])) for r in rows]
    return sorted(cases, key=lambda c: (c.reported_at, _seq(c.case_id)), reverse=True)


def get_trace(case_id: str) -> Optional[TraceResponse]:
    with _connect() as con:
        row = con.execute("SELECT trace FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return _aged(TraceResponse.model_validate_json(row[0])) if row else None


def get_case(case_id: str) -> Optional[CaseSummary]:
    with _connect() as con:
        row = con.execute("SELECT summary FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return _aged(CaseSummary.model_validate_json(row[0])) if row else None


def all_traces() -> dict:
    with _connect() as con:
        rows = con.execute("SELECT case_id, trace FROM cases").fetchall()
    return {cid: _aged(TraceResponse.model_validate_json(t)) for cid, t in rows}


# ---------- writes ----------
def add_case(req: TraceRequest, trace: TraceResponse) -> TraceResponse:
    """Store an engine result as a new case (next C-NNN id, B's recommendations added) and return it."""
    with _lock, _connect() as con:
        seq = (con.execute("SELECT MAX(seq) FROM cases").fetchone()[0] or 0) + 1
        case_id = f"C-{seq:03d}"
        trace = trace.model_copy(update={"case_id": case_id})
        network_id, linked = _network_for(con, case_id, trace)
        now = time.time()
        trace = with_recommendations(trace, linked, now)
        trace = trace.model_copy(update={"urgency_as_of": int(now), "monitoring": _monitoring(now)})
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
            urgency_as_of=trace.urgency_as_of,
            monitoring=trace.monitoring,
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


def watched_cases() -> List[str]:
    """Case ids the watcher should poll (those with monitoring on)."""
    return [c.case_id for c in list_cases() if c.monitoring and c.monitoring.status != "off"]


def reevaluate(case_id: str, now: Optional[float] = None,
               new_trace: Optional[TraceResponse] = None) -> Optional[Tuple[TraceResponse, TraceResponse]]:
    """One successful chain check: store the (optionally re-traced) case with fresh recommendations, urgency and
    'as of' time. Urgency can go down as well as up. Returns (old, new) traces, or None for an unknown case."""
    now = time.time() if now is None else now
    with _lock, _connect() as con:
        row = con.execute("SELECT summary, trace FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            return None
        summary, old = CaseSummary.model_validate_json(row[0]), TraceResponse.model_validate_json(row[1])
        base = old if new_trace is None else new_trace.model_copy(update={
            "case_id": case_id, "complaint_id": old.complaint_id, "fraud_type": old.fraud_type or new_trace.fraud_type})
        rows = con.execute("SELECT summary FROM cases").fetchall()
        nets = [json.loads(r[0]).get("network_id") for r in rows]
        linked = nets.count(summary.network_id) - 1 if summary.network_id else 0
        new = with_recommendations(base, linked, now)
        new = new.model_copy(update={"urgency_as_of": int(now), "monitoring": _monitoring(now)})
        status = summary.status
        if new.nearest_vasp and status in ("tracing", "unresolved"):
            status = "attributed"
        summary = summary.model_copy(update={
            "risk": new.risk, "urgency": new.urgency, "urgency_reasons": new.urgency_reasons,
            "urgency_as_of": new.urgency_as_of, "monitoring": new.monitoring, "status": status,
            "vasp": new.nearest_vasp.vasp if new.nearest_vasp else None,
            "time_to_attribution_sec": new.summary.time_to_attribution_sec or summary.time_to_attribution_sec})
        con.execute("UPDATE cases SET summary = ?, trace = ? WHERE case_id = ?",
                    (summary.model_dump_json(), new.model_dump_json(), case_id))
    return old, new


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
