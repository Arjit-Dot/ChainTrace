# ChainTrace

A blockchain tracer for cybercrime investigators (i4c). Given a wallet reported in a fraud complaint, ChainTrace follows the stolen USDT forward across wallets, shows the fund flow as a graph, and (as the later steps land) names the exchange that holds the money, scores risk, and drafts a freeze notice.

## Status

| Piece | State |
|---|---|
| API contract and all `/api` routes | done (`backend/contract/schemas.py`, `backend/main.py`) |
| TRON chain adapter (TronGrid, cache first) | done (`backend/chains/tron.py`) |
| Tracing engine (best-first, stop rules, pass-through, idle funds) | done (`backend/tracing.py`) |
| Case store, recommendations, case urgency (act now / act soon / preserve), dashboard, networks, freeze notice, React frontend | done |
| Attribution (nearest exchange) | done (`backend/attribution.py`) |
| Live monitoring: watcher, urgency "as of", alerts (demo feed is a recorded replay) | done (`backend/alerts.py`, `engine.new_transfers`) |
| Downstream wallet risk and typology (the reported wallet is not scored) | not built; placeholders |

The demo data is partly fictional: the hero case (`TUNoHG…`), "Example Exchange A/B/C" and the seed cases are scripted. The cache also holds three real wallets that Tether blacklisted. See `data/cache/SOURCES.md` and `data/LABELS.md`.

## Layout

```
backend/      FastAPI app (main.py), engine seam (engine.py), tracer (tracing.py), chains/tron.py, tests/
frontend/     React + Vite + Tailwind + Cytoscape UI
data/         labels.csv, vasp_contacts.csv, seed cases, fixtures, cache/ (TronGrid responses)
CONTRACT.md   the API contract and change process
DEMO.md       the build plan and progress log
```

## Set up locally

Requirements: Python 3.12, Node 18+.

```bash
# 1. backend dependencies
python3.12 -m venv env
source env/bin/activate
pip install -r requirements.txt

# 2. optional: TronGrid key (works without one, from the cache, or rate-limited live)
cp .env.example .env        # then paste the key from trongrid.io

# 3. frontend dependencies
cd frontend && npm install && cd ..
```

## Run

Two terminals:

```bash
# backend, on :8000  (docs at http://localhost:8000/docs)
cd backend
ENGINE_MODE=engine uvicorn main:app --reload --port 8000

# frontend, on :5173 (proxies /api to :8000)
cd frontend
npm run dev
```

Open http://localhost:5173, go to **New Complaint**, and submit wallet `TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo` with amount `12000`. You get the traced fund-flow graph ending at Example Exchange A.

### Engine modes

`ENGINE_MODE` picks where traces come from:

- `fixture` (default): prebuilt traces; no engine needed.
- `engine`: the real tracer in `backend/engine.py`. With no `TRONGRID_API_KEY` it reads only `data/cache/`, so wallets outside the cache show a single node. Set `TRACING=fixture` to use the old fixture inside engine mode.
- `http`: a separate engine at `ENGINE_URL`.

If the engine fails, the API falls back to the fixture and says so in the trace `notes`.

## Try live monitoring

With `ENGINE_MODE=engine`, submit wallet `TJgNArE5dkoiDgHUjimdizwNaTZZwLh1Lg` (amount `6000`). The case shows **Act now** (5,900 USDT idle). Click **Simulate fund movement**: a recorded transfer (SIMULATED) moves the funds to Example Exchange B, the alerts appear, and the badge drops to **Act soon**. The urgency card shows an "as of" time and a live/stale indicator; the backend polls every 30 seconds (`CHAINTRACE_POLL_SEC`, and `CHAINTRACE_MONITOR=0` turns the watcher off).

## Try the tracer on its own

```bash
cd backend
python -m tracing TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo 12000
```

Refill or extend the cache for a wallet: `python -m chains.tron --help`.

## Tests

```bash
cd backend && python -m pytest -q
```

All tests run offline.
