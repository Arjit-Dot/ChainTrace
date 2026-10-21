"""
Dashboard and network analytics (Person B, B7), computed from the case store on every request.

GET /api/dashboard  totals, % with an exchange identified, average time to attribution, idle funds, and
                    breakdowns by fraud type / receiving exchange / state.
GET /api/networks   complaints linked by shared scammer wallets (product/linking.py), one Network per linked
                    group: complaint -> shared wallet -> exchange.
"""
from collections import Counter, defaultdict
from typing import Dict, List

from fastapi import APIRouter

from contract.schemas import CaseSummary, CountItem, DashboardStats, Network, NetworkEdge, NetworkNode, TraceResponse
from product import store
from product.linking import case_groups, linking_wallets

router = APIRouter(prefix="/api", tags=["analytics"])


def _breakdown(cases: List[CaseSummary], key) -> List[CountItem]:
    count, amount = Counter(), defaultdict(float)
    for c in cases:
        k = key(c)
        if k:
            count[k] += 1
            amount[k] += c.amount_lost
    return [CountItem(name=k, count=n, amount=round(amount[k], 2))
            for k, n in sorted(count.items(), key=lambda kv: (-kv[1], -amount[kv[0]], kv[0]))]


def dashboard_stats() -> DashboardStats:
    cases = store.list_cases()
    traces = store.all_traces()
    timed = [c.time_to_attribution_sec for c in cases if c.time_to_attribution_sec is not None]
    return DashboardStats(
        total_cases=len(cases),
        open_cases=sum(c.open for c in cases),
        closed_cases=sum(not c.open for c in cases),
        total_amount_lost=round(sum(c.amount_lost for c in cases), 2),
        total_amount_traced=round(sum(t.summary.total_traced for t in traces.values()), 2),
        vasp_identified_pct=round(100 * sum(c.vasp is not None for c in cases) / len(cases), 1) if cases else 0.0,
        avg_time_to_attribution_sec=round(sum(timed) / len(timed), 1) if timed else 0.0,
        idle_funds_flagged=round(sum(t.summary.idle_funds for t in traces.values()), 2),
        by_fraud_type=_breakdown(cases, lambda c: c.fraud_type),
        top_vasps=_breakdown(cases, lambda c: c.vasp),
        by_state=_breakdown(cases, lambda c: c.state),
    )


def _wallet_label(wallet: str, traces: List[TraceResponse]) -> str:
    for t in traces:
        if t.nearest_vasp and t.nearest_vasp.deposit_address == wallet:
            return f"Shared deposit address ({t.nearest_vasp.vasp})"
    node = next((n for t in traces for n in t.graph.nodes if n.id == wallet), None)
    if node is not None and node.type == "scam_wallet":
        return "Shared reported wallet"
    return "Shared pass-through wallet"


def build_networks() -> List[Network]:
    cases = {c.case_id: c for c in store.list_cases()}
    traces = store.all_traces()
    out: List[Network] = []
    used = {c.network_id for c in cases.values() if c.network_id}
    for group in case_groups(traces):
        if len(group) < 2:
            continue
        ids = sorted(group)
        members = [cases[i] for i in ids if i in cases]
        ids_net = Counter(c.network_id for c in members if c.network_id)
        net = ids_net.most_common(1)[0][0] if ids_net else f"NET-{len(used) + len(out) + 1}"

        # Only wallets two or more of these complaints share: that is what links them (leaves add noise).
        holders: Dict[str, List[str]] = defaultdict(list)
        for i in ids:
            for w in linking_wallets(traces[i]):
                holders[w].append(i)
        shared = sorted(w for w, hs in holders.items() if len(hs) > 1)

        group_traces = [traces[i] for i in ids]
        nodes = [NetworkNode(id=i, type="complaint", label=f"{cases[i].complaint_id} ({cases[i].state})")
                 for i in ids if i in cases]
        nodes += [NetworkNode(id=w, type="wallet", label=_wallet_label(w, group_traces)) for w in shared]
        edges = [NetworkEdge(source=i, target=w) for w in shared for i in sorted(holders[w])]

        exchanges = {}  # deposit address -> exchange, for shared deposit addresses
        for t in group_traces:
            if t.nearest_vasp and t.nearest_vasp.deposit_address in shared:
                exchanges[t.nearest_vasp.deposit_address] = t.nearest_vasp.vasp
        for vasp in sorted(set(exchanges.values())):
            nodes.append(NetworkNode(id=f"vasp-{net}-{vasp}", type="exchange", label=vasp))
        edges += [NetworkEdge(source=w, target=f"vasp-{net}-{v}") for w, v in sorted(exchanges.items())]

        vasps = Counter(c.vasp for c in members if c.vasp)
        out.append(Network(
            network_id=net, complaint_ids=ids, victim_count=len(members),
            total_amount=round(sum(c.amount_lost for c in members), 2),
            states=sorted({c.state for c in members}), vasp=vasps.most_common(1)[0][0] if vasps else None,
            nodes=nodes, edges=edges))
    return sorted(out, key=lambda n: int(n.network_id.split("-")[1]) if n.network_id[4:].isdigit() else 0)


@router.get("/dashboard", response_model=DashboardStats)
def dashboard():
    return dashboard_stats()


@router.get("/networks", response_model=List[Network])
def networks():
    return build_networks()
