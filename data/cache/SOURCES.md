# data/cache sources

Every file in `data/cache/tron/` is a raw TronGrid response (`GET /v1/accounts/{address}/transactions/trc20?contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`), wrapped with `address`, `origin` and `fetched_at`.

## Real wallets (live TronGrid data)

Flagged = frozen by Tether on the USDT-TRC20 contract (`AddedBlackList` event). This is public and verifiable on-chain; Tether does not publish the reason for each freeze, so these are *flagged* wallets, not proven scam wallets. The raw event is saved in `blacklist_events/<address>.json`.

| # | Address | Blacklisted | Blacklist tx | USDT transfers cached | Outgoing | Volume (USDT) | Next hop cached |
|---|---|---|---|---|---|---|---|
| 1 | `TLhouDRQGCVB6xLuao86ky5Ns8FyoStg4z` | 2026-10-20 01:18 UTC | [7773112d0c2c…](https://tronscan.org/#/transaction/7773112d0c2c87dc70ca0578386fada735481657b62e72fd0788524bfb776642) | 69 | 19 | 4,209,410.31 | `TRNg56wy…`, `TW8A5iWM…`, `TNAYzWgn…` |
| 2 | `TP6jUy5qZedW2KZpJfFEEAbGVyD9kQXn6k` | 2026-10-20 01:18 UTC | [bb1c8b6fed80…](https://tronscan.org/#/transaction/bb1c8b6fed80cf23b7648d36b562ebb0cee6756ed0ae16e2a44fdc4b64629e35) | 22 | 12 | 2,708,518.27 | `TXobwGJQ…`, `TLL6qxRK…` |
| 3 | `TJhpBRFXNSoFpe6ek2opbrGhU21e8eCxJu` | 2026-10-20 01:18 UTC | [c5b99ff65619…](https://tronscan.org/#/transaction/c5b99ff65619660033431f5951c82422b01094cb2087ccd57de3f8a55edbc505) | 21 | 15 | 2,956,462.18 | `TVE2Uxrr…`, `TVKxxMgx…` |

Picked by `data/scripts/scamWallet.py` on 2026-10-20: the most recent blacklisted wallets with at least 10 USDT transfers and 3 outgoing (so there is something to trace). The 3 biggest recipients of each are cached too, so a 2-hop trace runs offline. Cached files of unlabeled addresses are *not* claims about their owners.

## Scripted hero case (fictional)

Files with `"origin": "scripted-hero"` are written by `data/scripts/make_hero_cache.py`. They are fictional (addresses derived from seed strings, the same as `data/fixtures/trace_hero.json`) and describe the agreed hero case C-001 in TronGrid format.

## Attribution scenarios (fictional)

Files with `"origin": "scripted-scenario"` are written by `data/scripts/make_attribution_scenarios.py` (expected results in `data/scenarios.json`, checked by `backend/tests/test_scenarios.py`). They use the fictional exchange, bridge and mixer labels from `labels.csv`.
