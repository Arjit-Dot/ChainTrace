"""Step 6.1: the seven wallet features, on hand-built transfer lists and on the cached hero wallets."""
import pytest

from engine.chains.tron import TronAdapter
from engine.model.features import FEATURE_NAMES, NEVER_FORWARDED_SEC, extract_features
from tests.support import T0, tx

W = "WALLET"


def test_feature_order_matches_the_dataclass():
    f = extract_features(W, [tx("A", W, 100, T0)])
    assert list(f.as_dict()) == FEATURE_NAMES and len(f.as_list()) == 7


def test_unrelated_and_empty_lists_give_zeros():
    f = extract_features(W, [tx("A", "B", 100, T0)])
    assert f.tx_count == 0 and f.unique_senders == 0 and f.in_out_ratio == 0 and f.median_forward_sec == NEVER_FORWARDED_SEC
    assert extract_features(W, []).tx_count == 0


def test_age_is_measured_at_arrival_not_now():
    ts = [tx("A", W, 100, T0), tx("B", W, 100, T0 + 2 * 86400)]
    assert extract_features(W, ts, arrival_ts=T0 + 86400).age_days == 1.0
    assert extract_features(W, ts).age_days == 2.0                      # default: last transfer
    assert extract_features(W, ts, arrival_ts=T0 - 500).age_days == 0.0  # never negative
    assert extract_features(W, [tx("A", W, 100, T0)], arrival_ts=T0).age_days == 0.0


def test_tx_count_counts_both_directions():
    ts = [tx("A", W, 100, T0), tx(W, "B", 90, T0 + 10), tx("X", "Y", 5, T0)]
    assert extract_features(W, ts).tx_count == 2


def test_in_out_ratio():
    assert extract_features(W, [tx("A", W, 1000, T0), tx(W, "B", 950, T0 + 5)]).in_out_ratio == 0.95
    assert extract_features(W, [tx("A", W, 1000, T0)]).in_out_ratio == 0.0                 # idle
    assert extract_features(W, [tx(W, "B", 500, T0)]).in_out_ratio == 0.0                  # nothing received
    assert extract_features(W, [tx("A", W, 100, T0), tx(W, "B", 300, T0 + 1)]).in_out_ratio == 1.0  # capped


def test_median_forward_time():
    ts = [tx("A", W, 100, T0), tx("B", W, 100, T0 + 1000),
          tx(W, "C", 100, T0 + 300), tx(W, "D", 100, T0 + 1600)]
    # first deposit waits 300 s, second waits 600 s -> median 450
    assert extract_features(W, ts).median_forward_sec == 450.0


def test_median_forward_ignores_deposits_never_followed_and_defaults_when_idle():
    ts = [tx("A", W, 100, T0), tx(W, "C", 100, T0 + 60), tx("B", W, 100, T0 + 5000)]  # 2nd deposit never forwarded
    assert extract_features(W, ts).median_forward_sec == 60.0
    assert extract_features(W, [tx("A", W, 100, T0)]).median_forward_sec == NEVER_FORWARDED_SEC


def test_unique_senders_counts_distinct_wallets():
    ts = [tx("A", W, 10, T0), tx("A", W, 10, T0 + 1), tx("B", W, 10, T0 + 2), tx(W, "A", 5, T0 + 3)]
    assert extract_features(W, ts).unique_senders == 2


def test_round_number_ratio():
    ts = [tx("A", W, 7850, T0), tx("B", W, 8000.0, T0 + 1), tx(W, "C", 1888.92, T0 + 2), tx(W, "D", 50, T0 + 3)]
    assert extract_features(W, ts).round_number_ratio == 0.75            # 7850, 8000, 50 are multiples of 50
    assert extract_features(W, [tx("A", W, 101.5, T0)]).round_number_ratio == 0.0


def test_fan_in_degree():
    many_in = [tx(f"S{i}", W, 10, T0 + i) for i in range(6)] + [tx(W, "H", 55, T0 + 100)]
    assert extract_features(W, many_in).fan_in_degree == 6.0            # 6 senders / 1 recipient
    split = [tx("A", W, 100, T0), tx(W, "B", 50, T0 + 1), tx(W, "C", 50, T0 + 2)]
    assert extract_features(W, split).fan_in_degree == 0.5
    assert extract_features(W, [tx("A", W, 100, T0)]).fan_in_degree == 1.0   # no recipients: divide by 1


def test_does_not_depend_on_input_order():
    ts = [tx("A", W, 100, T0), tx(W, "B", 95, T0 + 30), tx("C", W, 50, T0 + 90)]
    assert extract_features(W, ts) == extract_features(W, list(reversed(ts)))


# ---- the cached hero data (a pass-through wallet vs a busy deposit address)
@pytest.fixture(scope="module")
def adapter():
    return TronAdapter(offline=True)


def test_hero_pass_through_wallet_looks_like_a_mule(adapter):
    addr = "TMhTyFX8dfbnrswVFDYwoM6bXz1LjZ3ZXt"
    f = extract_features(addr, adapter.transfers(addr)[0], arrival_ts=1792400000)
    assert f.unique_senders == 1 and f.age_days == 0.0
    assert f.in_out_ratio == 0.9875 and f.median_forward_sec == 420.0   # 8000 in; 7850 + 50 out, first one 7 min later


def test_hero_deposit_address_has_many_senders(adapter):
    addr = "TAD47AKhQdrF4P8xpbVBx3GAr6Q56BFZJ3"
    f = extract_features(addr, adapter.transfers(addr)[0])
    assert f.unique_senders == 14 and f.fan_in_degree == 14.0 and f.age_days > 2
