# Label set notes (`labels.csv`, `vasp_contacts.csv`)

**`labels.csv`**: `address, chain, entity, type, source, note`
- `chain` uses the contract's `Chain` values (`tron`, `ethereum`, ...).
- `type` is a contract node type (`exchange`, `bridge`, `mixer`), or `swap` for DEX pools. A swap pool is not a VASP; the engine treats it as an intermediary hop with a `swap` edge.
- Rows with source `fixture (fictional)` use the same seed-derived addresses as `data/fixtures/` and `data/seed_traces.json`. That way the hero case and the seed cases attribute the same way live and offline.
- The real rows came from A's Dune Analytics query. The entity names are **not independently verified**. The `note` column records an on-chain check of balance and activity, which shows the address *behaves* like a hot wallet but does not prove who owns it.

**Removed (2026-10-20).** These rows did not behave like exchange hot wallets on-chain: no USDT balance, and fewer than 200 transfers over weeks or months. A wrong exchange label would send a freeze request to the wrong VASP.

| Address | Claimed entity | On-chain check |
|---|---|---|
| `TK86Qm97uM848dMk8G7xNbJB7zG1uW3h1n` | Huobi | 0 USDT; last 200 transfers span ~59 days; last active 2026-08-27 |
| `TSaRZDiBPD8Rd5vrvX8a4zgunHczM9mj8S` | OKX | ~13k USDT; last 200 transfers span ~2 years; last active 2026-05-02 |
| `TTd9qHyjqiUkfTxe3gotbuTMpjU8LEbpkN` | Kraken | 0 USDT; last 200 transfers span ~1 year; last active 2026-09-21 |

**Still missing:** a *real* TRON bridge or mixer address with a verifiable public label. The demo uses the fictional Example Bridge and Example Mixer.

**`vasp_contacts.csv`**: `vasp, nodal_officer, designation, email, phone`. Every contact is a mock. The Example Exchange emails match `nearest_vasp.contact` in the fixtures.
