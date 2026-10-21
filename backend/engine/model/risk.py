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
from typing import Dict, List, Optional, Tuple

from contract.schemas import Graph, Node
from engine.chains.tron import detect_chain, is_tron_address
from engine.model.features import extract_features
from engine.model.scoring import NO_HISTORY_REASON, score_wallet
from engine.model.typology import classify_wallet

# type -> (risk, score, reason). These match the hero fixture's values.
LABELED = {
    "exchange_hot": ("Low", 0.05, "Labeled exchange hot wallet"),
    "exchange_deposit": ("Low", 0.12, "Behaves like an exchange deposit address"),
    "bridge": ("Medium", 0.45, "Cross-chain bridge contract"),
    "mixer": ("Critical", 0.91, "Known mixing service"),
    "dex": ("Medium", 0.40, "Decentralised exchange pool: funds were swapped, there is no account holder to ask or freeze"),
}
CARRIES_TYPOLOGY = {"High", "Critical"}
# A wallet on another chain that received money crossing a bridge from the traced flow. Not the model (which only reads
# TRON wallets): a fixed, context-based rule, the same values as the hero fixture.
BRIDGED = ("High", 0.74)


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

    types = {n.id: n.type for n in graph.nodes}
    bridged = {e.target for e in graph.edges if types.get(e.source) == "bridge"}
    sends = {e.source for e in graph.edges}
    nodes = []
    for n in graph.nodes:
        if n.hop >= 1 and n.chain != "tron" and n.id in bridged:
            reasons = ["Received bridged funds from the traced flow"] + (["No outflow yet"] if n.id not in sends else [])
            nodes.append(n.model_copy(update={"risk": BRIDGED[0], "risk_score": BRIDGED[1], "reasons": reasons,
                                              "typology": typology}))
            continue
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


def wallet_risk_for(address: str, adapter, labels: Dict[str, Tuple[str, str]],
                    deposit_addresses=frozenset()) -> Tuple[str, float, List[str], str]:
    """(risk, score, reasons, typology) for one address on its own, for GET /api/wallets/{address}/risk.

    Labeled exchange, bridge and mixer addresses get the fixed values; anything else is scored from its own transfers.
    There is no trace here, so age is measured to the wallet's last transfer, and the typology (only given to High and
    Critical wallets) comes from the wallet's own payments with no mixer information. An address we cannot score (not a
    TRON address, or no history available) is Low with a reason saying why: the contract has no 'unknown' level."""
    if not is_tron_address(address):
        chain = detect_chain(address)
        why = f"this is a {chain.capitalize()} address and only TRON wallets can be scored" if chain else "not a valid wallet address"
        return "Low", 0.0, [f"Not scored: {why}"], "unknown"
    label = labels.get(address)
    if label:
        kind = label[1]
        key = "exchange_deposit" if kind == "exchange" and address in deposit_addresses else "exchange_hot" if kind == "exchange" else kind
        risk, score, reason = LABELED[key]
        return risk, score, [reason], "unknown"
    try:
        transfers = adapter.transfers(address)[0]
    except (LookupError, ValueError):
        return "Low", 0.0, [NO_HISTORY_REASON], "unknown"
    truncated = bool(getattr(adapter, "history_truncated", lambda a: False)(address))
    r = score_wallet(extract_features(address, transfers), truncated=truncated)
    typology = classify_wallet(address, transfers).typology if r.level in CARRIES_TYPOLOGY else "unknown"
    return r.level, r.score, r.reasons, typology
