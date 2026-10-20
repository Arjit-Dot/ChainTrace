"""Attribution scenarios: every scripted case in data/scenarios.json run end to end through the engine seam."""
import json
from pathlib import Path

import pytest

import engine
from contract.schemas import TraceRequest

SCENARIOS = json.loads((Path(__file__).resolve().parents[2] / "data" / "scenarios.json").read_text())


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["key"] for s in SCENARIOS])
def test_scenario(sc):
    exp = sc["expect"]
    r = engine.trace_complaint(TraceRequest(complaint_id=f"SC-{sc['key']}", wallet=sc["wallet"], amount=sc["amount"]))
    v, ids = r.nearest_vasp, {n.id: n for n in r.graph.nodes}
    if exp["vasp"] is None:
        assert v is None and r.notes
    else:
        assert v.vasp == exp["vasp"] and v.method == exp["method"]
        assert v.deposit_address in ids and v.evidence
        for field in ("deposit_address", "hops"):
            if field in exp:
                assert getattr(v, field) == exp[field]
        if v.method == "heuristic":
            assert exp["conf_min"] <= v.confidence <= exp["conf_max"] < 0.90
        else:
            assert v.confidence >= 0.90
    if "idle" in exp:
        assert r.summary.idle_funds == exp["idle"]
    if "terminal" in exp:
        assert ids[exp["terminal"]].type in ("mixer", "bridge")
        assert not any(e.source == exp["terminal"] for e in r.graph.edges)
    assert r.summary.idle_funds == pytest.approx(sum(n.idle_balance for n in r.graph.nodes))
