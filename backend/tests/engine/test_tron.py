"""Chain adapter (Step 3): units, cache-first behaviour, address detection, and the cached data."""
import json
from pathlib import Path

import httpx
import pytest

from engine.chains.tron import USDT_TRC20, TronAdapter, detect_chain, hex_to_tron, is_tron_address, normalize
from paths import CACHE, FIXTURES, LABELS_CSV

HERO = json.loads((FIXTURES / "trace_hero.json").read_text())
ADDR = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
OTHER = "TJ4imTmNr3FZoqR2jsRBuXS2aNXNAsAXhK"


def raw(value="7850000000", ts_ms=1792400420000, token=USDT_TRC20, src=ADDR, dst=OTHER, tx="ab" * 32):
    return {"transaction_id": tx, "block_timestamp": ts_ms, "from": src, "to": dst, "type": "Transfer",
            "value": value, "token_info": {"symbol": "USDT", "address": token, "decimals": 6}}


def test_normalize_converts_to_contract_units():
    t = normalize(raw())
    assert t.amount == 7850.0 and isinstance(t.amount, float)
    assert t.timestamp == 1792400420  # seconds, not ms
    assert (t.from_addr, t.to_addr, t.token) == (ADDR, OTHER, "USDT")


def test_normalize_drops_other_tokens():
    assert normalize(raw(token="TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf")) is None


@pytest.mark.parametrize("address, chain", [
    (ADDR, "tron"),
    ("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6x", None),          # bad checksum
    ("0xd90e2f925da726b50c4ed8d0fb90ad053324f31b", "ethereum"),
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "bitcoin"),
    ("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", "bitcoin"),
    ("So11111111111111111111111111111111111111112", "solana"),
    ("not-an-address", None),
])
def test_detect_chain(address, chain):
    assert detect_chain(address) == chain


def test_hex_to_tron():
    assert hex_to_tron("0x75bfdc53b18902c3ca06da533687064ed56a37e3") == "TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z"


def test_cache_first_never_calls_network(tmp_path):
    def boom(request):
        raise AssertionError("network called despite cache")
    a = TronAdapter(cache_dir=tmp_path, client=httpx.Client(transport=httpx.MockTransport(boom)))
    a.write_cache(ADDR, [raw()])
    items, source = a.transfers(ADDR)
    assert source == "cached" and items[0].amount == 7850.0


def test_live_fallback_pages_and_writes_cache(tmp_path):
    pages = [
        {"success": True, "data": [raw(tx="01" * 32, ts_ms=2000)], "meta": {"fingerprint": "next"}},
        {"success": True, "data": [raw(tx="02" * 32, ts_ms=1000)], "meta": {}},
    ]
    calls = []

    def handler(request):
        calls.append(dict(request.url.params))
        return httpx.Response(200, json=pages[len(calls) - 1])

    client = httpx.Client(base_url="https://api.trongrid.io", transport=httpx.MockTransport(handler))
    a = TronAdapter(cache_dir=tmp_path, client=client)
    items, source = a.transfers(ADDR)
    assert source == "live" and len(calls) == 2 and calls[1]["fingerprint"] == "next"
    assert calls[0]["contract_address"] == USDT_TRC20
    assert [t.timestamp for t in items] == [1, 2]  # oldest first
    assert a.transfers(ADDR)[1] == "cached"


def test_offline_adapter_refuses_uncached(tmp_path):
    with pytest.raises(LookupError):
        TronAdapter(cache_dir=tmp_path, offline=True).transfers(ADDR)


def test_rejects_non_tron_address(tmp_path):
    with pytest.raises(ValueError):
        TronAdapter(cache_dir=tmp_path, offline=True).transfers("0xd90e2f925da726b50c4ed8d0fb90ad053324f31b")


# ---- the committed cache (Step 2 data) ----
def test_hero_cache_reproduces_fixture_transfers():
    a = TronAdapter(offline=True)
    chain = {n["id"]: n["chain"] for n in HERO["graph"]["nodes"]}
    for e in HERO["graph"]["edges"]:
        if chain[e["source"]] != "tron" or chain[e["target"]] != "tron":
            continue
        out = {t.tx_hash: t for t in a.outgoing(e["source"])}
        t = out[e["tx_hash"]]
        assert (t.to_addr, t.amount, t.timestamp) == (e["target"], e["amount"], e["timestamp"])


def test_hero_deposit_address_looks_like_a_deposit_address():
    a = TronAdapter(offline=True)
    deposit = HERO["nearest_vasp"]["deposit_address"]
    senders = {t.from_addr for t in a.incoming(deposit)}
    sweeps = {t.to_addr for t in a.outgoing(deposit)}
    assert len(senders) >= 14
    assert len(sweeps) == 1  # everything goes to the one hot wallet


def test_three_real_flagged_wallets_are_cached_and_documented():
    events = sorted((CACHE / "blacklist_events").glob("T*.json"))
    assert len(events) >= 3
    sources = (CACHE / "SOURCES.md").read_text()
    a = TronAdapter(offline=True)
    for p in events:
        addr = p.stem
        assert addr in sources
        assert hex_to_tron(json.loads(p.read_text())["result"]["_user"]) == addr
        transfers, source = a.transfers(addr)
        assert source == "cached" and any(t.from_addr == addr for t in transfers)


def test_hero_hot_wallet_is_labeled():
    import csv
    labels = {r["address"]: r for r in csv.DictReader(LABELS_CSV.open())}
    deposit = HERO["nearest_vasp"]["deposit_address"]
    hot = next(e["target"] for e in HERO["graph"]["edges"] if e["source"] == deposit)
    assert labels[hot]["entity"] == HERO["nearest_vasp"]["vasp"]
    assert all(is_tron_address(a) or detect_chain(a) == r["chain"] for a, r in labels.items())
    assert {r["type"] for r in labels.values()} <= {"exchange", "bridge", "mixer", "swap"}
    assert all(r["source"] for r in labels.values())


# ---- truncated history (a busy wallet has more transfers than one fetch returns)
def _paged_client(pages, calls):
    def handler(request):
        calls.append(dict(request.url.params))
        return httpx.Response(200, json=pages[len(calls) - 1])
    return httpx.Client(base_url="https://api.trongrid.io", transport=httpx.MockTransport(handler))


def test_fetch_stopped_by_the_limit_with_more_available_is_flagged_truncated(tmp_path):
    pages = [{"success": True, "data": [raw(tx=f"{i:02d}" * 32, ts_ms=1000 + i) for i in range(3)], "meta": {"fingerprint": "more"}}]
    a = TronAdapter(cache_dir=tmp_path, client=_paged_client(pages, []))
    items, source = a.transfers(ADDR, limit=3)
    assert source == "live" and len(items) == 3
    assert a.read_cache(ADDR)["truncated"] is True and a.history_truncated(ADDR) is True


def test_complete_history_is_not_flagged(tmp_path):
    pages = [{"success": True, "data": [raw(tx="aa" * 32, ts_ms=1000)], "meta": {}}]
    a = TronAdapter(cache_dir=tmp_path, client=_paged_client(pages, []))
    a.transfers(ADDR, limit=3)
    assert a.read_cache(ADDR)["truncated"] is False and a.history_truncated(ADDR) is False


def test_exactly_the_limit_with_no_more_pages_is_not_truncated(tmp_path):
    pages = [{"success": True, "data": [raw(tx=f"{i:02d}" * 32, ts_ms=1000 + i) for i in range(3)], "meta": {}}]
    a = TronAdapter(cache_dir=tmp_path, client=_paged_client(pages, []))
    a.transfers(ADDR, limit=3)
    assert a.history_truncated(ADDR) is False


def test_old_cache_files_without_the_flag_count_as_truncated_when_a_full_page(tmp_path):
    a = TronAdapter(cache_dir=tmp_path, offline=True)
    a.write_cache(ADDR, [raw(tx=f"{i:064d}") for i in range(200)])
    assert "truncated" not in a.read_cache(ADDR) and a.history_truncated(ADDR) is True
    a.write_cache(OTHER, [raw(tx=f"{i:064d}") for i in range(199)])
    assert a.history_truncated(OTHER) is False
    assert a.history_truncated("TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo") is False     # not in this cache dir: nothing to flag


def test_fetch_live_still_returns_a_plain_list(tmp_path):
    pages = [{"success": True, "data": [raw(tx="bb" * 32)], "meta": {}}]
    assert len(TronAdapter(cache_dir=tmp_path, client=_paged_client(pages, [])).fetch_live(ADDR)) == 1


def test_committed_real_cache_marks_the_busy_wallets_truncated():
    a = TronAdapter(offline=True)
    capped = [p.stem for p in (CACHE / "tron").glob("*.json")
              if len(json.loads(p.read_text())["data"]) >= 200]
    assert capped and all(a.history_truncated(addr) for addr in capped)
    assert not a.history_truncated("TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu")          # 21 transfers: complete
    assert not a.history_truncated("TMhTyFX8dfbnrswVFDYwoM6bXz1LjZ3ZXt")          # scripted hero wallet
