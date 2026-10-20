"""
Run from backend/:  pytest
Passes on the fixture stub today. Person A keeps it green while replacing engine.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import engine
from contract.schemas import TraceRequest

REQ = TraceRequest(complaint_id="NCRP-TEST", wallet="TXyz", amount=1000, fraud_type="investment")


def test_trace_shape():
    r = engine.trace_complaint(REQ)
    ids = {n.id for n in r.graph.nodes}
    assert r.graph.nodes, "graph must have nodes"
    for e in r.graph.edges:                      # every edge points at a real node
        assert e.source in ids and e.target in ids
    assert r.summary.nodes == len(r.graph.nodes)
    reported = next(n for n in r.graph.nodes if n.hop == 0)
    assert reported.label == "Reported" and reported.risk is None and reported.risk_score is None
    assert r.risk is None and r.risk_score is None and r.urgency is None  # engine leaves urgency to B
    for n in r.graph.nodes:
        if n.hop != 0:
            assert n.risk is not None and 0 <= n.risk_score <= 1


def test_nearest_vasp_is_in_graph():
    r = engine.trace_complaint(REQ)
    if r.nearest_vasp:
        assert r.nearest_vasp.deposit_address in {n.id for n in r.graph.nodes}
        assert r.nearest_vasp.evidence, "attribution must carry evidence"
        assert r.nearest_vasp.method in ("deterministic", "heuristic")


def test_idle_funds_consistent():
    r = engine.trace_complaint(REQ)
    assert abs(r.summary.idle_funds - sum(n.idle_balance for n in r.graph.nodes)) < 1e-6


def test_wallet_risk():
    w = engine.wallet_risk("TXyz")
    assert w.risk in ("Low", "Medium", "High", "Critical") and w.reasons
