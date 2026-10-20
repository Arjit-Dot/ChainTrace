"""
Which wallets link complaints into one network (Person B).

Two cases are linked when their traces share a wallet the scammers control: the reported
wallet, a pass-through wallet, or the exchange deposit address. Exchange hot wallets,
bridges and mixers are shared public infrastructure, so they never link cases on their own.

Used by the seed-trace checks now and by GET /api/networks in B7.
"""
from typing import Dict, List, Set

import networkx as nx

from contract.schemas import TraceResponse

LINKING_TYPES = {"scam_wallet", "intermediary"}


def linking_wallets(trace: TraceResponse) -> Set[str]:
    wallets = {n.id for n in trace.graph.nodes if n.type in LINKING_TYPES}
    if trace.nearest_vasp:
        wallets.add(trace.nearest_vasp.deposit_address)
    return wallets


def case_groups(traces: Dict[str, TraceResponse]) -> List[Set[str]]:
    """Connected components of the case <-> linking-wallet graph, as sets of case IDs."""
    g = nx.Graph()
    for case_id, trace in traces.items():
        g.add_node(("case", case_id))
        for w in linking_wallets(trace):
            g.add_edge(("case", case_id), ("wallet", w))
    return [{key for kind, key in comp if kind == "case"} for comp in nx.connected_components(g)]
