"""
Put risk scores, reasons and fraud typology onto a traced graph (Step 6.6).

  hop 0 (the reported wallet)   not scored: a victim already named it (risk stays null). It carries the case typology and
                                the reasons for it, so the panel can say why it looks like that kind of scam
  victims                       left as they are
  labeled endpoints             fixed values: exchange Low, bridge Medium, mixer Critical (the model does not score them)
  every other downstream wallet scored by the model from its own transfers (rules if there is no model); a wallet whose
                                history was only partly fetched is capped at Medium (see scoring.py)
The case typology comes from the reported wallet's behaviour; High and Critical wallets carry it.
"""
from typing import Dict, Optional, Tuple

from contract.schemas import Graph, Node
from engine.model.features import extract_features
from engine.model.scoring import NO_HISTORY_REASON, score_wallet
from engine.model.typology import classify_wallet

# type -> (risk, score, reason). These match the hero fixture's values.
LABELED = {
    "exchange_hot": ("Low", 0.05, "Labeled exchange hot wallet"),
    "exchange_deposit": ("Low", 0.12, "Behaves like an exchange deposit address"),
    "bridge": ("Medium", 0.45, "Cross-chain bridge contract"),
    "mixer": ("Critical", 0.91, "Known mixing service"),
}
CARRIES_TYPOLOGY = {"High", "Critical"}


def _fixed(node: Node) -> Optional[Tuple[str, float, str]]:
    if node.type == "exchange":
        return LABELED["exchange_deposit" if (node.label or "").endswith("(deposit address)") else "exchange_hot"]
    return LABELED.get(node.type)


def score_graph(graph: Graph, adapter, wallet: str) -> Tuple[Graph, str]:
    """(graph with risk, score, reasons and typology filled in for downstream wallets, case typology).

    `adapter` needs `transfers(address)` and may have `history_truncated(address)`. The input graph is not modified."""
    arrival: Dict[str, int] = {}
    for e in sorted(graph.edges, key=lambda e: e.timestamp):
        arrival.setdefault(e.target, e.timestamp)

    try:
        root_transfers = adapter.transfers(wallet)[0]
    except (LookupError, ValueError):
        root_transfers = []
    found = classify_wallet(wallet, root_transfers, graph)
    typology = found.typology

    nodes = []
    for n in graph.nodes:
        if n.hop == 0 and typology != "unknown":
            nodes.append(n.model_copy(update={"typology": typology, "reasons": found.reasons}))
            continue
        if n.hop < 1 or n.chain != "tron":                       # reported wallet, victims, and wallets we cannot read
            nodes.append(n)
            continue
        fixed = _fixed(n)
        if fixed:
            risk, score, reason = fixed
            nodes.append(n.model_copy(update={"risk": risk, "risk_score": score, "reasons": [reason]}))
            continue
        try:
            transfers = adapter.transfers(n.id)[0]
        except (LookupError, ValueError):
            transfers = []
        truncated = bool(getattr(adapter, "history_truncated", lambda a: False)(n.id)) if transfers else False
        r = score_wallet(extract_features(n.id, transfers, arrival.get(n.id)), truncated=truncated)
        nodes.append(n.model_copy(update={
            "risk": r.level, "risk_score": r.score, "reasons": r.reasons,
            "typology": typology if r.level in CARRIES_TYPOLOGY else "unknown"}))
    return Graph(nodes=nodes, edges=graph.edges), typology
