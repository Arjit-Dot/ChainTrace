"""Case urgency (B4): act_now > act_soon > preserve, first match wins, reasons list the triggers."""
import json
from pathlib import Path

from contract.schemas import TraceResponse
from recommendations import build_urgency, with_recommendations

ROOT = Path(__file__).resolve().parents[2]
HERO = TraceResponse(**json.loads((ROOT / "data" / "fixtures" / "trace_hero.json").read_text()))
LAST_TX = max(e.timestamp for e in HERO.graph.edges)
LONG_AFTER = LAST_TX + 3 * 86400


def variant(**changes):
    """The hero with its idle funds zeroed (so lower tiers can be reached), plus `changes`."""
    nodes = [n.model_copy(update={"idle_balance": 0.0}) for n in HERO.graph.nodes]
    summary = HERO.summary.model_copy(update={"idle_funds": 0.0})
    return HERO.model_copy(update={"graph": HERO.graph.model_copy(update={"nodes": nodes}),
                                   "summary": summary, **changes})


def test_hero_is_act_now_because_of_idle_funds():
    urgency, reasons = build_urgency(HERO, now=LONG_AFTER)
    assert urgency == "act_now" and "3,720 USDT idle in a wallet" in reasons[0]


def test_recent_outgoing_transaction_is_act_now():
    assert build_urgency(variant(), now=LAST_TX + 3600)[0] == "act_now"
    assert build_urgency(variant(), now=LAST_TX + 25 * 3600)[0] != "act_now"


def test_funds_unswept_at_deposit_address_is_act_now():
    dep = HERO.nearest_vasp.deposit_address
    edges = [e for e in HERO.graph.edges if e.source != dep]
    t = variant(graph=HERO.graph.model_copy(update={"edges": edges}))
    urgency, reasons = build_urgency(t, now=LONG_AFTER)
    assert urgency == "act_now" and "not been swept" in reasons[0]


def test_act_soon_triggers():
    base = variant(nearest_vasp=None, amount_lost=500.0)
    assert build_urgency(base, now=LONG_AFTER)[0] == "preserve"
    assert build_urgency(base.model_copy(update={"amount_lost": 10_000.0}), now=LONG_AFTER)[0] == "act_soon"
    assert build_urgency(base, linked_complaints=2, now=LONG_AFTER)[0] == "act_soon"
    assert build_urgency(base, linked_complaints=1, now=LONG_AFTER)[0] == "preserve"
    weak = base.model_copy(update={"nearest_vasp": HERO.nearest_vasp.model_copy(update={"confidence": 0.69})})
    assert build_urgency(weak, now=LONG_AFTER)[0] == "preserve"
    strong = base.model_copy(update={"nearest_vasp": HERO.nearest_vasp.model_copy(update={"confidence": 0.70})})
    assert build_urgency(strong, now=LONG_AFTER)[0] == "act_soon"


def test_first_match_wins_and_lists_every_trigger_of_that_tier():
    t = variant(amount_lost=20_000.0)
    urgency, reasons = build_urgency(t, linked_complaints=3, now=LONG_AFTER)
    assert urgency == "act_soon" and len(reasons) == 3          # VASP + amount + linked
    assert build_urgency(HERO.model_copy(update={"amount_lost": 20_000.0}), now=LONG_AFTER)[0] == "act_now"


def test_preserve_has_a_reason():
    t = variant(nearest_vasp=None, amount_lost=100.0)
    urgency, reasons = build_urgency(t, now=LONG_AFTER)
    assert urgency == "preserve" and reasons


def test_with_recommendations_sets_urgency_fields():
    out = with_recommendations(HERO.model_copy(update={"urgency": None, "urgency_reasons": []}), now=LONG_AFTER)
    assert out.urgency == "act_now" and out.urgency_reasons and out.recommendations
