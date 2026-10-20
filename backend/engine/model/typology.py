"""
Fraud typology (Step 6.5): which kind of scam a reported wallet looks like, from how its money came in and left.

Rule-assisted: a small set of signatures, checked in order, first match wins, otherwise `unknown`. Every threshold is
a PLACEHOLDER chosen from how these scams usually look, to be tuned by investigators; the signatures are our
assumptions, not measured facts. The complaint's own `fraud_type` is not used: this is what the chain behaviour says.
`darknet` has no signature and is never returned.

  ransomware        a few large payments, and much of the money goes to a mixer
  sextortion        many different payers, each paying a small amount once
  task_scam         many payers, small amounts, the same victims paying again and again, consolidated fast
  phishing          a brand-new wallet receiving a few non-round (drained-balance) payments and forwarding at once
  investment_scam   several payers, mid to large amounts, consolidated fast
"""
import statistics
from dataclasses import dataclass
from typing import List, Optional

from contract.schemas import Graph
from engine.chains.tron import Transfer
from engine.model.features import extract_features

# ---- placeholders ---------------------------------------------------------------------------------------
RANSOM = {"max_deposits": 5, "min_median": 10_000, "min_mixer_share": 0.20}
SEXTORTION = {"min_senders": 15, "max_median": 200, "max_repeat_share": 0.30}
TASK = {"min_senders": 10, "max_median": 500, "min_repeat_share": 0.30, "max_forward_sec": 24 * 3600}
PHISHING = {"max_deposits": 8, "max_age_days": 2.0, "max_forward_sec": 3600, "min_median": 200, "max_round_share": 0.30}
INVESTMENT = {"min_senders": 2, "min_median": 500, "max_forward_sec": 24 * 3600, "min_forwarded": 0.70}
ESTABLISHED_DAYS = 120    # a wallet this old is not a fresh scam collector: say unknown rather than guess


@dataclass(frozen=True)
class DepositProfile:
    deposits: int
    unique_senders: int
    median_deposit: float        # amount-weighted: the payment size in which the typical dollar arrived
    max_deposit: float
    repeat_share: float          # share of deposits made by a payer who paid more than once
    age_days: float
    tx_count: int
    median_forward_sec: float
    forwarded_share: float       # amount sent / amount received, capped at 1
    round_number_ratio: float
    mixer_share: float           # share of the traced money that reached a mixer


@dataclass(frozen=True)
class TypologyResult:
    typology: str
    reasons: List[str]


def mixer_share(graph: Optional[Graph]) -> float:
    """Money that entered a mixer, as a share of everything that moved onward from a non-victim wallet."""
    if graph is None:
        return 0.0
    types = {n.id: n.type for n in graph.nodes}
    onward = sum(e.amount for e in graph.edges if types.get(e.source) != "victim")
    mixed = sum(e.amount for e in graph.edges if types.get(e.target) == "mixer")
    return round(mixed / onward, 4) if onward > 0 else 0.0


def _dollar_median(amounts: List[float]) -> float:
    """Median payment size weighted by amount, so a few dust payments cannot drag the typical size down."""
    total = sum(amounts)
    if total <= 0:
        return float(statistics.median(amounts)) if amounts else 0.0
    acc = 0.0
    for a in sorted(amounts):
        acc += a
        if acc >= total / 2:
            return float(a)
    return float(max(amounts))


def deposit_profile(addr: str, transfers: List[Transfer], arrival_ts: Optional[int] = None,
                    graph: Optional[Graph] = None) -> DepositProfile:
    f = extract_features(addr, transfers, arrival_ts)
    dep = [t for t in transfers if t.to_addr == addr]
    per_sender = {}
    for t in dep:
        per_sender[t.from_addr] = per_sender.get(t.from_addr, 0) + 1
    repeat = sum(c for c in per_sender.values() if c > 1) / len(dep) if dep else 0.0
    amounts = [t.amount for t in dep]
    typical = _dollar_median(amounts)
    return DepositProfile(
        deposits=len(dep), unique_senders=f.unique_senders,
        median_deposit=typical, max_deposit=max(amounts, default=0.0),
        repeat_share=round(repeat, 4), age_days=f.age_days, tx_count=f.tx_count, median_forward_sec=f.median_forward_sec,
        forwarded_share=f.in_out_ratio, round_number_ratio=f.round_number_ratio, mixer_share=mixer_share(graph))


def classify(p: DepositProfile) -> TypologyResult:
    """First matching signature wins."""
    if p.deposits == 0 or p.age_days >= ESTABLISHED_DAYS:
        return TypologyResult("unknown", ["No inbound payments to learn from" if p.deposits == 0
                                          else "Established wallet: not a fresh scam collector"])
    fast = p.median_forward_sec

    if p.deposits <= RANSOM["max_deposits"] and p.median_deposit >= RANSOM["min_median"] and p.mixer_share >= RANSOM["min_mixer_share"]:
        return TypologyResult("ransomware", [f"{p.deposits} large payments (median {p.median_deposit:,.0f} USDT)",
                                             f"{p.mixer_share:.0%} of the money went into a mixer"])
    if p.unique_senders >= SEXTORTION["min_senders"] and p.median_deposit <= SEXTORTION["max_median"] \
            and p.repeat_share < SEXTORTION["max_repeat_share"]:
        return TypologyResult("sextortion", [f"{p.unique_senders} different payers",
                                             f"Small payments (median {p.median_deposit:,.0f} USDT), rarely repeated"])
    if p.unique_senders >= TASK["min_senders"] and p.median_deposit <= TASK["max_median"] \
            and p.repeat_share >= TASK["min_repeat_share"] and fast <= TASK["max_forward_sec"]:
        return TypologyResult("task_scam", [f"{p.unique_senders} payers making small repeated payments "
                                            f"({p.repeat_share:.0%} from repeat payers)", "Consolidated within a day"])
    if p.deposits <= PHISHING["max_deposits"] and p.age_days < PHISHING["max_age_days"] and fast <= PHISHING["max_forward_sec"] \
            and p.median_deposit >= PHISHING["min_median"] and p.round_number_ratio <= PHISHING["max_round_share"]:
        return TypologyResult("phishing", ["Brand-new wallet", "A few non-round payments, as from drained balances",
                                           "Forwarded within the hour"])
    if p.unique_senders >= INVESTMENT["min_senders"] and p.median_deposit >= INVESTMENT["min_median"] \
            and fast <= INVESTMENT["max_forward_sec"] and p.forwarded_share >= INVESTMENT["min_forwarded"]:
        return TypologyResult("investment_scam", [f"{p.unique_senders} payers, median payment {p.median_deposit:,.0f} USDT",
                                                  "Consolidated fast"])
    return TypologyResult("unknown", ["No known scam pattern matched"])


def classify_wallet(addr: str, transfers: List[Transfer], graph: Optional[Graph] = None,
                    arrival_ts: Optional[int] = None) -> TypologyResult:
    return classify(deposit_profile(addr, transfers, arrival_ts, graph))
