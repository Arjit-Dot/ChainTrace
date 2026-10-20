"""
Attribution engine (Step 5): name the exchange that holds the money and say how sure we are.

Direct match: the trace reaches an address labeled as an exchange (`deterministic`).
Sweep heuristic: the wallet just before a labeled hot wallet looks like a customer deposit address
(many different senders, forwards its balance to the hot wallet), so it is the account to freeze (`heuristic`).
"""
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from contract.schemas import Edge, Graph, NearestVASP, Node
from engine.chains.tron import Transfer
from paths import CONTACTS_CSV, LABELS_CSV

SWEEP_RATIO = 0.90        # share of received funds forwarded to the hot wallet
MIN_SENDERS = 5           # distinct senders for a deposit-address pattern
SENDER_CAP = 15           # sender count at which the sweep signal saturates
HEURISTIC_CAP = 0.89      # heuristic-only results never reach 0.90
DIRECT_CONFIDENCE = 0.95
WEIGHTS = {"label_match": 0.4, "sweep_count": 0.3, "counterparty_diversity": 0.2}


def load_contacts(path: Path = CONTACTS_CSV) -> Dict[str, str]:
    """vasp name -> nodal contact email."""
    with open(path, newline="") as f:
        return {r["vasp"]: r["email"] for r in csv.DictReader(f)}


def deposit_addresses(path: Path = LABELS_CSV) -> set:
    """Labeled addresses that are published customer deposit addresses (not the exchange's own hot wallet)."""
    with open(path, newline="") as f:
        return {r["address"] for r in csv.DictReader(f) if "deposit address" in (r.get("note") or "")}


def vasp_name(label: Optional[str]) -> Optional[str]:
    """'Example Exchange A (hot wallet)' -> 'Example Exchange A'."""
    return re.sub(r"\s*\(.*\)\s*$", "", label).strip() if label else None


def confidence(label_match: float, sweep_count: float, diversity: float) -> float:
    """Weighted sum of the three signals, each 0-1, capped below 0.90 (heuristic only)."""
    score = (WEIGHTS["label_match"] * label_match + WEIGHTS["sweep_count"] * sweep_count
             + WEIGHTS["counterparty_diversity"] * diversity)
    return round(min(score, HEURISTIC_CAP), 2)


def sweep_stats(history: List[Transfer], addr: str, hot: str, graph_ids: set) -> Optional[dict]:
    """Does `addr` look like a deposit address that sweeps into `hot`? None if it does not."""
    incoming = [t for t in history if t.to_addr == addr]
    senders = {t.from_addr for t in incoming}
    received = sum(t.amount for t in incoming)
    swept = sum(t.amount for t in history if t.from_addr == addr and t.to_addr == hot)
    if len(senders) < MIN_SENDERS or received <= 0 or swept < SWEEP_RATIO * received:
        return None
    stamps = [t.timestamp for t in incoming]
    return {"senders": len(senders), "unrelated": len(senders - graph_ids), "ratio": swept / received,
            "span_hours": round((max(stamps) - min(stamps)) / 3600), "swept_txs": sum(
                1 for t in history if t.from_addr == addr and t.to_addr == hot)}


def _inbound(graph: Graph, addr: str) -> Optional[Edge]:
    """The largest traced transfer into `addr`."""
    edges = [e for e in graph.edges if e.target == addr]
    return max(edges, key=lambda e: e.amount, default=None)


def attribute(graph: Graph, adapter, labels: Dict[str, Tuple[str, str]],
              contacts: Optional[Dict[str, str]] = None) -> Tuple[Optional[NearestVASP], Graph]:
    """Return (NearestVASP or None, graph with the deposit node retyped as an exchange)."""
    contacts = load_contacts() if contacts is None else contacts
    ids = {n.id for n in graph.nodes}
    by_id = {n.id: n for n in graph.nodes}
    exchanges = sorted((n for n in graph.nodes if n.hop >= 0 and labels.get(n.id, ("", ""))[1] == "exchange"),
                       key=lambda n: n.hop)
    for hot in exchanges:
        vasp = labels[hot.id][0]
        # sweep heuristic: a predecessor of the hot wallet that looks like a deposit address
        for edge in (e for e in graph.edges if e.target == hot.id):
            dep = by_id.get(edge.source)
            if dep is None or dep.hop < 1 or dep.id in labels:
                continue
            try:
                stats = sweep_stats(adapter.transfers(dep.id)[0], dep.id, hot.id, ids)
            except LookupError:
                continue
            into = _inbound(graph, dep.id)
            if stats is None or into is None:
                continue
            conf = confidence(1.0, min(stats["senders"] / SENDER_CAP, 1.0), stats["unrelated"] / stats["senders"])
            evidence = [
                f"Deposit address received funds from {stats['senders']} different wallets over {stats['span_hours']} hours",
                f"It forwarded {stats['ratio']:.0%} of what it received to the labeled hot wallet "
                f"in {stats['swept_txs']} transfers",
                f"Hot wallet {hot.id[:8]}... is labeled {vasp}",
            ]
            dep.type, dep.label = "exchange", f"{vasp} (deposit address)"
            return NearestVASP(vasp=vasp, deposit_address=dep.id, hops=dep.hop, amount=into.amount,
                               timestamp=into.timestamp, confidence=conf, method="heuristic",
                               evidence=evidence, contact=contacts.get(vasp_name(vasp))), graph
        # direct match: the trace itself reached a labeled exchange address
        into = _inbound(graph, hot.id)
        if into is not None:
            hot.label = hot.label or (f"{vasp} (deposit address)" if hot.id in deposit_addresses() else vasp)
            return NearestVASP(vasp=vasp, deposit_address=hot.id, hops=hot.hop, amount=into.amount,
                               timestamp=into.timestamp, confidence=DIRECT_CONFIDENCE, method="deterministic",
                               evidence=[f"Funds were sent directly to {hot.id[:8]}..., labeled {vasp} in the label set"],
                               contact=contacts.get(vasp_name(vasp))), graph
    return None, graph
