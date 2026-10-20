"""
The seven features of a wallet (DEMO.md Step 6), computed from its USDT transfers.

All of them are deterministic functions of the transfer list, so cached data always gives the same numbers.
Time is measured at the moment funds arrived (`arrival_ts`), not "now", because the demo data is fictional and old.
"""
import statistics
from dataclasses import astuple, dataclass, asdict
from typing import Dict, List, Optional, Tuple

from engine.chains.tron import Transfer

FEATURE_NAMES = ["age_days", "tx_count", "in_out_ratio", "median_forward_sec",
                 "unique_senders", "round_number_ratio", "fan_in_degree"]
NEVER_FORWARDED_SEC = 7 * 86400   # median_forward_sec when the wallet never forwarded anything
ROUND_STEP = 50                   # an amount that is a multiple of 50 USDT counts as "round"


@dataclass(frozen=True)
class WalletFeatures:
    age_days: float            # days from the wallet's first transfer to when funds arrived
    tx_count: int              # transfers touching the wallet
    in_out_ratio: float        # amount sent / amount received, capped at 1 (0 when nothing was received)
    median_forward_sec: float  # amount-weighted median seconds from money arriving to the next outgoing transfer
    unique_senders: int        # distinct wallets that paid it
    round_number_ratio: float  # share of its transfers with round amounts
    fan_in_degree: float       # unique senders / unique recipients (consolidation)

    def as_list(self) -> List[float]:
        return [float(v) for v in astuple(self)]

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


def _is_round(amount: float) -> bool:
    q = amount / ROUND_STEP
    return abs(q - round(q)) < 1e-9


def _weighted_median(waits: List[Tuple[float, float]]) -> float:
    """Median wait where each deposit counts in proportion to its amount, so one old dust deposit cannot
    outweigh the large deposit that was forwarded in minutes. Equal amounts give the usual lower median."""
    total = sum(w for _, w in waits)
    if total <= 0:
        return float(statistics.median(t for t, _ in waits))
    acc = 0.0
    for t, w in sorted(waits):
        acc += w
        if acc >= total / 2:
            return float(t)
    return float(waits[-1][0])


def extract_features(addr: str, transfers: List[Transfer], arrival_ts: Optional[int] = None) -> WalletFeatures:
    """Features of `addr` from `transfers` (any list; transfers not touching `addr` are ignored).

    `arrival_ts` is when the traced funds reached the wallet (default: its last transfer)."""
    mine = sorted((t for t in transfers if addr in (t.from_addr, t.to_addr)), key=lambda t: (t.timestamp, t.tx_hash))
    if not mine:
        return WalletFeatures(0.0, 0, 0.0, float(NEVER_FORWARDED_SEC), 0, 0.0, 0.0)
    incoming = [t for t in mine if t.to_addr == addr]
    outgoing = [t for t in mine if t.from_addr == addr]

    ref = mine[-1].timestamp if arrival_ts is None else arrival_ts
    age_days = max(0.0, (ref - mine[0].timestamp) / 86400)

    received = sum(t.amount for t in incoming)
    sent = sum(t.amount for t in outgoing)
    in_out = min(sent / received, 1.0) if received > 0 else 0.0

    waits = []   # (seconds until the next outgoing transfer, size of the deposit)
    for t in incoming:
        nxt = next((o.timestamp for o in outgoing if o.timestamp >= t.timestamp), None)
        if nxt is not None:
            waits.append((nxt - t.timestamp, t.amount))
    median_forward = _weighted_median(waits) if waits else float(NEVER_FORWARDED_SEC)

    senders = {t.from_addr for t in incoming}
    recipients = {t.to_addr for t in outgoing}
    return WalletFeatures(
        age_days=round(age_days, 4),
        tx_count=len(mine),
        in_out_ratio=round(in_out, 4),
        median_forward_sec=median_forward,
        unique_senders=len(senders),
        round_number_ratio=round(sum(_is_round(t.amount) for t in mine) / len(mine), 4),
        fan_in_degree=round(len(senders) / max(len(recipients), 1), 4),
    )
