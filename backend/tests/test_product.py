"""Product-side checks (Person B): seed cases and seed traces agree with each other and the contract."""
import json
from collections import defaultdict
from pathlib import Path

import pytest

from contract.schemas import CaseSummary, TraceResponse
from linking import case_groups

DATA = Path(__file__).resolve().parents[2] / "data"
CASES = [CaseSummary(**c) for c in json.loads((DATA / "seed_cases.json").read_text())]
TRACES = {k: TraceResponse(**v) for k, v in json.loads((DATA / "seed_traces.json").read_text()).items()}


def test_every_seed_case_has_a_trace():
    assert {c.case_id for c in CASES} == set(TRACES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_trace_matches_case(case):
    t = TRACES[case.case_id]
    assert (t.complaint_id, t.wallet, t.risk) == (case.complaint_id, case.wallet, case.risk)
    assert (t.nearest_vasp.vasp if t.nearest_vasp else None) == case.vasp
    assert t.summary.time_to_attribution_sec == case.time_to_attribution_sec


@pytest.mark.parametrize("case_id", sorted(TRACES))
def test_trace_follows_contract_rules(case_id):
    t = TRACES[case_id]
    ids = {n.id for n in t.graph.nodes}
    assert all(e.source in ids and e.target in ids for e in t.graph.edges)
    assert t.summary.nodes == len(t.graph.nodes)
    assert t.summary.idle_funds == pytest.approx(sum(n.idle_balance for n in t.graph.nodes))
    assert any(n.id == t.wallet and n.hop == 0 for n in t.graph.nodes)
    if t.nearest_vasp:
        assert t.nearest_vasp.deposit_address in ids
        assert t.nearest_vasp.evidence
        assert t.nearest_vasp.method == ("deterministic" if t.nearest_vasp.confidence >= 0.9 else "heuristic")


def test_networks_from_shared_wallets_match_network_ids():
    expected = defaultdict(set)
    for c in CASES:
        expected[c.network_id or c.case_id].add(c.case_id)  # unlinked cases stand alone
    found = sorted(sorted(g) for g in case_groups(TRACES))
    assert found == sorted(sorted(g) for g in expected.values())
    assert sum(len(g) > 1 for g in found) >= 2
