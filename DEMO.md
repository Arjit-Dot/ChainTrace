# ChainTrace: 2-Day Demo Build Guide

> A compact, visual, end-to-end demo of a Real-Time Crypto Fraud Attribution System. It touches every area in the problem statement at surface level and goes deep on one thing: **complaint → trace → "which exchange got the money" → freeze request.**

---

## 1. Context

**The problem.** Victims of cyber-fraud in India report crypto wallet addresses on NCRP / 1930. Fraudsters move funds through burner wallets, bridges and swaps within minutes. Manual tracing is slow, so exchanges (VASPs) are contacted too late.

**What ChainTrace is (and isn't).**
- It **is** an attribution and lead-generation tool. It finds the exchange or VASP that received funds, so investigators can send a freeze/KYC request while some money may still be there.
- It **is not** a tool that recovers all money or identifies the criminal from the chain alone. Wallets carry no identity; the exchange's KYC data is the bridge to real people and to the bank/UPI mule layer.

**Why exchanges are the chokepoint.** Crypto is only useful to a fraudster once cashed out. That conversion point (exchange, P2P, OTC) is where KYC exists.

**Where AI fits.** The tracing and attribution core is deterministic (explainable, court-defensible). AI handles risk scoring, wallet classification, fraud typology, anomaly detection and network linking.

---

## 2. Demo Goal and Success Criteria

In a **5-minute demo** the audience should see:

1. A complaint arrives with a wallet address.
2. The system traces the funds and draws a fund-flow graph.
3. It names the receiving exchange with a confidence score and evidence.
4. Downstream wallets get a risk level, fraud type, and reason codes (AI); the reported wallet is labeled `Reported`.
5. The case gets an urgency level (Act now / Act soon / Preserve) with the reasons that triggered it.
6. A freeze request and PDF evidence report are generated.
7. Continuous monitoring watches the open wallets; when funds move, the case is re-checked and an alert changes the urgency badge live.
8. A dashboard shows cases and a linked criminal network.

**Rule for the 2 days:** use **cached/seeded data as the backbone** so the demo never breaks, and add one **live TRON trace** as a bonus. Label clearly in the UI what is live and what is simulated.

---

## 3. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **Python 3.11 + FastAPI** | One language for API, tracing, ML, reports; auto OpenAPI docs double as the integration spec |
| Graph logic | **NetworkX** | No infrastructure; enough for demo-size graphs |
| Storage | **SQLite** | Zero setup; swap to PostgreSQL later |
| Chain data | **TronGrid API** (live bonus) + **cached JSON** (backbone) | Reliable demo, real data proof |
| ML | **scikit-learn + XGBoost + SHAP** | Tabular data, needs explainability |
| Frontend | **React (Vite) + Tailwind CSS** | Fast to build, looks polished |
| Graph viz | **Cytoscape.js** | Purpose-built for network graphs |
| Charts | **Recharts** | Simple dashboard charts |
| Reports | **ReportLab** | PDF generation in Python |
| Real-time | **Server-Sent Events (SSE)** | Simplest way to push alerts to the UI |

---

## 4. Coverage Map: Problem Statement vs Demo

| Required topic | In the demo | Real or simulated |
|---|---|---|
| Ingest wallets from complaint systems | Complaint form + mock NCRP feed endpoint | Simulated feed, real API |
| Automatic blockchain tracing | Forward trace, 3-5 hops | **Real** (TRON live + cached) |
| Identify exchange/VASP | Label DB + sweep heuristic + confidence | **Real logic**, small label set |
| Fund movement patterns | Pass-through / layering detection | **Real logic** |
| Clustering of exchange wallets | Deposit-address clustering via sweeps | **Real logic** |
| Cross-chain movement | Bridge detection + link to destination chain | Seeded example |
| Mixers / DeFi / bridges | Flagged as terminal nodes with warnings | Label-based |
| Risk categorization | Low/Medium/High/Critical on downstream wallets + SHAP reasons | **Real model**, trained on synthetic + seed data |
| Case urgency | Act now / Act soon / Preserve from rules, with the triggers shown | **Real logic**, placeholder thresholds |
| Fraud typology | Investment / sextortion / ransomware / phishing | Rule-assisted ML |
| Continuous monitoring and alerts | Watchlist of leaf and idle wallets, polled; re-trace, attribution and urgency re-run on new transfers; alerts via SSE | **Real watcher**; the demo feed is a recorded transaction replay, labeled SIMULATED |
| SAHYOG / NCRP integration | Mock connectors + API spec | Simulated |
| Investigative recommendations | Rule-based action list | **Real** |
| Fund-flow visualization | Interactive graph | **Real** |
| Analytics dashboard | KPIs, charts, network view | Seeded data |
| Standardized reports | PDF evidence report + freeze notice | **Real** |
| Multi-chain support | Adapter interface, TRON + one EVM stub | TRON real, EVM seeded |

---

## 5. Project Structure

Same structure as the original: `backend/`, `data/`, `frontend/`. Every file has exactly one owner, shown in the comment (**A** = Engine, **B** = Product, **Shared** = frozen after kickoff). See section 11.

```
chaintrace/
├── backend/
│   ├── main.py                    # B: all /api routes (run: cd backend && uvicorn main:app)
│   ├── paths.py                   # Shared: where every data file lives (import paths from here)
│   ├── contract/                  # Shared: schemas.py = the contract as Pydantic models (frozen, DONE)
│   ├── engine/                    # A: everything that produces findings
│   │   ├── __init__.py            #    the seam: trace_complaint, wallet_risk, new_transfers, replay (DONE except risk)
│   │   ├── chains/tron.py         #    TronGrid adapter + cache (DONE)
│   │   ├── trace/                 #    tracing.py: forward trace + pass-through (DONE); attribution.py: labels, sweep heuristic, confidence (DONE)
│   │   └── model/                 #    risk.py: features, model, SHAP, typology (A6, to build)
│   ├── product/                   # B: everything built from the findings
│   │   ├── engine_client.py       #    calls the engine, or returns a pre-built trace
│   │   ├── store.py               #    SQLite case store (stands in for the planned db.py)
│   │   ├── recommendations.py     #    action list + case urgency
│   │   ├── linking.py             #    groups complaints into networks
│   │   ├── notices.py             #    freeze notice (templates/ holds the Jinja template)
│   │   ├── alerts.py              #    live monitoring watcher, SSE alert stream, scripted demo alerts, new-case alerts
│   │   ├── analytics.py           #    dashboard and network analytics computed from the case store
│   │   ├── integrations.py        #    mock NCRP and SAHYOG endpoints
│   │   ├── reports.py             #    PDF evidence report (ReportLab + matplotlib), SHA-256 evidence hash
│   │   └── export_openapi.py      #    writes docs/openapi.json
│   └── tests/
│       ├── contract/              # engine output matches the contract
│       ├── engine/                # A: tron adapter, tracing, attribution, attribution scenarios (risk tests come with A6)
│       ├── product/               # B: seed cases, case store, urgency, live monitoring
│       └── support.py             # shared fakes for tests
├── data/
│   ├── reference/                 # A: labels.csv (exchanges, mixers, bridges), LABELS.md, vasp_contacts.csv (mock nodal contacts)
│   ├── cache/                     # A: tron/ (3 flagged wallets + next hops + scripted hero + scenarios), SOURCES.md
│   ├── scenarios/                 # A: scenarios.json (attribution test cases) + replay_movements.json (live-monitoring demo feed)
│   ├── models/                    # A: risk_model.pkl (A6, to build)
│   ├── seed/                      # B: seed_cases.json (8 demo complaints) + seed_traces.json (one pre-built trace each)
│   ├── fixtures/                  # Shared: contract fixtures, one per endpoint (frozen)
│   │   └── trace_hero.json        #    the hero example response
│   │   # also: cases, dashboard, networks, alerts, wallet_risk_hero, freeze_notice_hero, ncrp_ack, sahyog_ack, report_sample.pdf
│   └── scripts/                   # build scripts: gen_fixtures.py (Shared), make_seed_traces.py (B), make_hero_cache.py,
│                                  #    make_attribution_scenarios.py, scamWallet.py (A)
├── frontend/                      # B: React + Tailwind + Cytoscape
│   └── src/                       #    components/common (layout, badges, status), components/case (graph, panels, cards), pages, hooks, lib
├── docs/                          # openapi.json (the integration spec); archive/ holds the original contract pack zips
├── CONTRACT.md                    # Shared: the contract in plain language
├── DEMO.md                        # this plan
├── README.md                      # what the project is and how to run it
├── pytest.ini                     # run `pytest` from the repo root or from backend/
├── slides.pptx                    # A
└── requirements.txt               # Shared file; A and B each keep their own block of lines
```

---

## 6. Day 1: Engine (Backend + Data)

> **How to read sections 6 and 7:** this is the full build reference, in logical order. It is **not** a schedule. With two people the steps run in parallel and are split into tasks **A1-A8** (Engine) and **B1-B8** (Product). Each step names its owner; section 11 gives the order and clock times.

### Step 1. Project setup (1 hr)
**Owner:** kickoff (both) + A1 (backend) + B1 (frontend)
**What:** Repo, environment, folder structure, API keys.
**How:**
- Kickoff (together): repo, the structure from section 5, `CONTRACT.md` and `backend/contract/schemas.py`, the pinned `requirements.txt`, and `backend/main.py` with `/api/health` and every contract route on fixtures (all supplied by the contract pack).
- A: create the virtual environment (`python3.12 -m venv env`, the folder is git-ignored as `env/`), then `pip install -r requirements.txt` (it already includes `scikit-learn xgboost shap pytest`). Create a free TronGrid API key and store it in `.env` (git-ignored; **not created yet**).
- B: `reportlab matplotlib` are already in `requirements.txt`; install it, then scaffold the frontend (Vite, Tailwind, Cytoscape.js, Recharts).
- Both: run `cd backend && uvicorn main:app --reload --port 8000`, and confirm `/api/health` and `/docs` load and `pytest` passes.

### Step 2. Seed data (2 hrs)
**Owner:** A1 (pick wallets) + A3 (cache, labels, contacts, hero case) + B3 (seed cases)
**What:** The data that makes the demo reliable.
**How:**
- **(A)** Pick **3 real TRON scam/laundering wallets** from public sources (e.g., publicly flagged addresses on Tronscan) and save their TronGrid responses into `data/cache/` (the Step 3 adapter does the saving).
- **(A)** Build `labels.csv` with columns `address, chain, entity, type, source`. Include 4-5 major exchanges' known hot wallets, 1-2 mixer/bridge addresses, and note the source of every label. Also build `vasp_contacts.csv` (one mock nodal contact per exchange).
- **(B)** Create `seed_cases.json` with 8-10 complaints (complaint ID, wallet, amount, fraud type, state), using synthetic addresses. Give every case its own pre-built trace in `seed_traces.json`, in the contract format (`TraceResponse`), so the dashboard and Network View never wait for the engine. Some should share a downstream wallet so the network feature has something to find.
- **(A)** Create one **fully scripted case** where the trace clearly ends at an exchange; this is your hero demo. **(B)** uses the same hero wallet (agreed at kickoff) for the New Complaint example.

### Step 3. Chain adapter (2 hrs)
**Owner:** A2
**What:** Fetch and normalize transactions.
**How:**
- Call TronGrid: `GET /v1/accounts/{addr}/transactions/trc20?contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t&limit=200` (USDT-TRC20; 6 decimals; timestamps in ms; the contract wants seconds and float token units, so convert here).
- Normalize to `Transfer(tx_hash, from, to, amount, timestamp)`, in the contract's units: timestamps in Unix epoch **seconds** (UTC), amounts as token-unit floats (`7850.0` = 7,850 USDT), never raw integers with decimals.
- Always try the cache first; fall back to live; save live results to the cache.
- Add address-format detection (TRON `T…`, Ethereum `0x…`, Bitcoin `1/3/bc1…`) to show multi-chain routing, even if only TRON is fully implemented. Chain values must be from the contract's `Chain` enum: `tron, ethereum, bsc, polygon, bitcoin, solana`.

### Step 4. Tracing engine (3 hrs)
**Owner:** A4
**What:** Follow money forward and stop at meaningful endpoints.
**How:**
- Best-first search: a priority queue ordered by value and recency, starting from the reported wallet.
- Add each outgoing transfer as a graph edge. Stop expanding at: known exchange, mixer, bridge, depth 5, or flows under 1% of the case value.
- **Pass-through detection:** tag a wallet `intermediary` if it forwards ≥90% of what it receives within ~1 hour.
- Check balances of leaf nodes; a leaf still holding funds gets an "idle funds" flag.
- Output the graph in the contract format (`Graph` in `schemas.py`): nodes (`id` = address, `chain`, `type`, `label`, `hop`, `risk`, `risk_score`, `reasons`, `typology`, `idle_balance`) and edges (`source`, `target`, `tx_hash`, `amount`, `token`, `timestamp`, `edge_type`). Node `type` is one of `victim, scam_wallet, intermediary, bridge, mixer, exchange, unknown`; `hop` is `-1` for victims, `0` for the reported wallet, increasing downstream; `summary.idle_funds` must equal the sum of node `idle_balance`. The reported wallet (hop 0) is labeled `Reported` and its `risk` and `risk_score` are `null`; risk is scored on downstream wallets only.

### Step 5. Attribution engine (3 hrs)
**Owner:** A5
**What:** Name the exchange and score the confidence.
**How:**
- **Direct match:** destination address found in `labels.csv`.
- **Sweep heuristic:** if a candidate deposit address receives from many unrelated wallets and forwards its balance to a labeled hot wallet, attribute it to that exchange.
- **Confidence score:** weighted sum of `label_match`, `sweep_count`, `counterparty_diversity`. Cap heuristic-only results below 0.90 and set `method` to `heuristic`; a direct label match is `deterministic`. Confidence is a 0-1 float.
- Return a `NearestVASP` object: `vasp`, `deposit_address`, `hops`, `amount`, `timestamp`, `confidence`, `method`, `evidence[]` (never empty), `contact` from `vasp_contacts.csv`. Its `deposit_address` must exist in the graph. Return `null` when no exchange is found.

**End of Day 1 checkpoint:** `POST /api/trace` with a wallet returns a graph plus a Nearest VASP result for the hero case. This is A's acceptance test; B switches to the real engine at Checkpoint 1 (11.6).

---

## 7. Day 2: AI, Outputs, Interface

### Step 6. AI risk and typology (2.5 hrs)
**Owner:** A6
**What:** Risk level for downstream wallets, fraud type, reason codes.
**How:**
- **Scope:** the reported wallet is already suspected because a victim named it, so it is not scored (`risk: null`, labeled `Reported`). Risk is scored on downstream wallets, to show which hops to follow first.
- **Features per wallet:** age, tx count, in/out ratio, median time-to-forward, unique senders, round-number ratio, fan-in degree.
- **Training data:** generate a synthetic labeled set (scam collectors vs normal vs exchange-like) using realistic ranges, plus your seed wallets. Be upfront in the UI and slides that the model is trained on synthetic + seed data for the demo.
- Train XGBoost; map probability to Low/Medium/High/Critical; compute SHAP top-3 reasons ("forwards funds in 4 minutes", "89 unique senders").
- **Typology:** rule-assisted classifier using signatures: many small deposits + fast consolidation → `investment_scam` / `task_scam`; many unique tiny senders → `sextortion`; few large payments + mixer → `ransomware`. Allowed typology values: `investment_scam, task_scam, sextortion, ransomware, phishing, darknet, unknown`.
- Expose `GET /api/wallets/{address}/risk`, returning `WalletRisk` (`address, risk, risk_score, reasons, typology`); `risk_score` is 0 to 1.

### Step 7. Reports and recommendations (2 hrs)
**Owner:** B4 (recommendations, freeze notice) + B5 (PDF report)
**What:** Turn findings into actions.
**How:**
- **Case urgency** (output `urgency: act_now | act_soon | preserve` and `urgency_reasons[]` on the case; set by B in `recommendations.py` from the trace data, no ML). First match wins, top to bottom:
  1. `act_now`: any of: idle funds at the last check (`summary.idle_funds > 0`); funds reached a VASP deposit address and have not been swept out yet; a fresh outgoing transfer was observed from a case wallet in the last 15 minutes.
  2. `act_soon`: any of: a VASP was identified at confidence 0.70 or higher (funds already swept to its hot wallet); amount lost is 10,000 or more; the case is linked to 2 or more complaints.
  3. `preserve`: everything else (funds entered a mixer, no VASP found, or an old trail with no idle funds).
  `urgency_reasons[]` lists the triggers that fired, so an officer can see why. The thresholds (15 minutes, 0.70, 10,000, 2 complaints) are placeholders for the demo; real values should come from investigators.
  **As of and re-evaluation.** There is no provisional stage: urgency is computed once the trace finishes and kept current by monitoring (Step 8). `urgency_as_of` is the time of the last successful chain check, not of the last change, so a quiet case still shows a fresh time. `monitoring` is `{status: live | stale | off, last_checked_at, poll_interval_sec}`; `stale` means the last check is older than about twice the poll interval, so the badge cannot claim freshness it does not have. Urgency can go down as well as up: if idle funds move, `act_now` may drop to `act_soon` or `preserve`, and the reasons show why. `act_now` means a freeze is possible in this window, not guaranteed. Recommendation `priority` only orders the recommendations panel; the UI shows the urgency badge, not a second scale.
- **Recommendation rules** (output `recommendations[]` of `{priority: urgent|high|normal, action, detail}`): idle funds found → "act immediately"; VASP found ≥ threshold → "issue freeze/KYC request to X"; mixer reached → "preserve evidence, monitor exits"; bridge reached → "continue on destination chain".
- **Freeze notice:** text template filled with complaint ID, tx hashes, addresses, amounts, times; request freeze **plus** preservation of KYC, bank, phone and IP data. Leave legal-section references as placeholders. Served by `GET /api/cases/{case_id}/freeze-notice` as a `FreezeNotice` (`case_id, to_vasp, to_email, subject, body, requested_actions, status: draft|approved|sent`).
- **PDF evidence report (ReportLab):** summary, graph image, transaction table, attribution evidence, methodology and limitations, SHA-256 hash of the report. Served by `GET /api/cases/{case_id}/report` as a PDF.

### Step 8. Alerts and mock integrations (1.5 hrs)
**Owner:** B6
**What:** Real-time feel and integration story.
**How:**
- **Live watcher** (`backend/product/alerts.py`, B): once a case is traced, its leaf and idle wallets go on a watchlist and are polled for new transfers (placeholder: every 30 seconds) through `engine_client.new_transfers`, which calls the engine's `new_transfers(addresses, since_ts)`. Every poll re-evaluates urgency and updates `urgency_as_of`. When a new transfer appears the system (1) extends the graph by re-tracing, (2) re-runs attribution and urgency, (3) updates the "as of" time, (4) pushes an alert. A failed check changes nothing, so the case goes `stale` instead of looking fresh.
- `GET /api/alerts/stream` using SSE (event name `alert`, data = `Alert` JSON), plus `GET /api/alerts` for history. Alert types: `FUNDS_MOVED, REACHED_VASP, ENTERED_MIXER, NEW_COMPLAINT_LINKED, HIGH_RISK_WALLET, URGENCY_CHANGED` (the message carries the old and new level).
- **Demo mode:** with no TronGrid key there is no live feed, so a recorded transaction replay (`data/scenarios/replay_movements.json`) stands in for it, and `POST /api/cases/{case_id}/simulate-movement` (the "Simulate fund movement" button) releases it, runs the check now and pushes the alerts. This is labeled SIMULATED. `POST /api/alerts/simulate` still replays a fixture alert.
- `POST /api/integrations/ncrp/complaints`: accepts a `TraceRequest` (NCRP-style payload), starts a trace, returns an `IntegrationAck`. `POST /api/integrations/sahyog/notice`: accepts a `SahyogNoticeRequest` and returns an `IntegrationAck`.
- Export the OpenAPI spec as the integration contract.

### Step 9. Frontend (5 hrs)
**Owner:** B1 (scaffold), B2 (Case View), B3 (New Complaint), B7 (Dashboard, Network View), B8 (animation)
**What:** The part judges see.
**How:**
- **Pages:** (1) Dashboard, (2) New Complaint, (3) Case View, (4) Network View.
- **Case View:** Cytoscape graph with colors by node type (victim grey, scam wallet red, intermediary orange, bridge blue, mixer purple, exchange green, unknown white); edge thickness = amount; click a node for risk, reasons and transactions. Add a "Nearest VASP" card, an urgency badge (Act now / Act soon / Preserve) with its reasons, an "as of 14:32:10" time and a live / stale indicator (a stale case gets a visible warning; the page refreshes on every alert for the case), a recommendations panel, and **Download Report / Freeze Notice** buttons.
- **Dashboard (Recharts):** KPI tiles from `GET /api/dashboard` (`total_cases`, `total_amount_traced`, `avg_time_to_attribution_sec`, `vasp_identified_pct`, `idle_funds_flagged`), `by_fraud_type`, `top_vasps`, `by_state`, and a live alert feed.
- **Network View:** group seed complaints that share downstream wallets into one network graph (use `networkx.connected_components`), served by `GET /api/networks` as `Network[]`.
- Use a dark theme, a consistent color legend, and a short animation as the trace builds hop by hop; it makes the speed visible.

### Step 10. Polish and rehearsal (2 hrs)
**Owner:** B8 (Demo Mode, badges) + A8 (slides) + both (rehearsal, recording)
**What:** A demo that cannot fail.
**How:**
- Add a "Demo Mode" toggle that forces cached data.
- Mark each result with its `source` field (`live`, `cached` or `simulated`) as a badge.
- Prepare 5-6 slides from sections 8 and 9 (A8).
- Rehearse the script below three times with a timer.
- Record a screen capture as a backup.

---

## 8. 5-Minute Demo Script

| Time | Action | Message |
|---|---|---|
| 0:00 | Show the problem in one sentence | "Funds vanish in minutes; tracing takes days." |
| 0:30 | Submit a complaint (or trigger the mock NCRP feed) | "Starts from the complaint, no analyst needed." |
| 1:00 | Watch the graph build hop by hop | "Real-time forward tracing." |
| 2:00 | Open the Nearest VASP card | "Exchange, deposit address, confidence, evidence." |
| 2:45 | Show urgency badge and reasons, then downstream risk, fraud type, SHAP reasons | "AI prioritizes; evidence stays explainable." |
| 3:15 | Generate freeze notice + PDF report | "Ready to send in one click." |
| 3:45 | Simulate fund movement: the alert fires and the urgency badge changes live | "If funds move, we know, and the case re-prioritizes itself." |
| 4:15 | Open the Network View | "These complaints, one organized network." |
| 4:45 | State limits and what's next | "Attribution and leads, not a magic recovery tool." |

---

## 9. What to Be Honest About in the Demo

- Label database is small; real deployment needs a much larger one.
- Risk model is trained on synthetic + seed data for the demo.
- NCRP/SAHYOG links are simulated.
- The tool finds the exchange; the exchange's KYC data links to people and the fiat/mule layer.
- Mixers and privacy tools are flagged, not "solved".
- "Live" means polling: there is always a delay of up to one poll interval plus block confirmation time. The demo's movement is a recorded replay, labeled SIMULATED.
- Public APIs have rate limits, so only leaf and idle wallets are watched, not the whole graph.
- Live monitoring improves how current the reading is. It cannot make `act_now` mean a freeze will succeed.

---

## 10. Priority if Time Runs Short

Cut in this order (last items first): Network View → alerts → ML model (fallback to rule-based scoring) → live TRON trace. **Never cut:** graph, Nearest VASP card, freeze notice/report.

---

## 11. Team Split: Two People, Working Independently

**Person A: Engine.** Owns everything that *produces* findings: chain data, tracing, attribution, risk/AI. The engine is **stateless**: a complaint goes in, a trace result comes out. No database, no UI. One extra light function supports live monitoring: `new_transfers(addresses, since_ts)` returns the new transfers of a few wallets so B's watcher need not re-run a full trace on every poll.
**Person B: Product.** Owns everything built *from* the findings: interface, database, recommendations, reports, alerts, mock integrations, seed cases, dashboard, demo mode.

A and B are connected by **one thing only: the contract** (`CONTRACT.md` and `backend/contract/schemas.py`, version `CONTRACT_VERSION`). Every file, folder and endpoint has exactly one owner. Neither person waits for the other: B builds against fixtures, A tests with scripts.

Tasks are numbered **A1-A8** and **B1-B8**, in the order each person does them. The "Step" column maps each task back to the build reference in sections 6 and 7.

### 11.1 Rules that keep A and B independent

1. **One shared artifact: the contract.** To change it: tell the other person first, edit `schemas.py` and bump `CONTRACT_VERSION`, update `data/scripts/gen_fixtures.py` and run it, run `cd backend && pytest`, then merge together. Prefer additive changes (a new optional field); nothing is renamed or removed without that process. B never asks A for something the contract does not contain.
2. **One owner per file** (11.2). Never edit the other person's files. If you need a change there, message them.
3. **A is stateless, B owns persistence.** A never touches the database. B never reads `data/cache/`, `data/reference/labels.csv`, `data/reference/vasp_contacts.csv` or the model file; B only displays what the engine returns.
4. **B touches the engine only through the seam.** The seam is `backend/engine/__init__.py`: `trace_complaint(req: TraceRequest) -> TraceResponse`, `wallet_risk(address) -> WalletRisk` and (added with contract v1.1.0) `new_transfers(addresses, since_ts) -> list[Transfer]`. B never imports A's other modules (everything in `backend/engine/` except the seam itself: `chains/`, `trace/`, `model/`) and A never changes the seam's signatures. B calls the seam from `main.py`, or reaches it over HTTP via `backend/product/engine_client.py`, which has two modes:
   - `fixture` (default): returns a pre-built trace from `data/fixtures/trace_hero.json` or `data/seed/seed_traces.json`. B works with no engine at all.
   - `http`: calls the engine (the same server after A merges, or A's laptop before that).
5. **Each person tests alone.** A: scripts and `pytest`. B: fixtures. Both check their output against the same contract.
6. **Separate branches** `engine` and `product`, merged into `main` only at sync points. No file has two owners, so merges do not conflict.
7. **Bug triage:** if the engine's output does not match the contract, it is A's bug. If a fixture matches the contract but the UI breaks, it is B's bug.

### 11.2 Ownership

| | Person A: Engine | Person B: Product |
|---|---|---|
| Build steps | 1 (backend), 2 (cache, labels, contacts, hero case), 3, 4, 5, 6, 10 (slides) | 1 (frontend), 2 (seed cases), 7, 8, 9, 10 (demo mode) |
| Backend files | `backend/engine/` (the seam is `engine/__init__.py`; A edits only this package): `chains/`, `trace/`, `model/`; `tests/engine/`, `tests/contract/` | `main.py` (routes), `backend/product/` (`engine_client.py`, `store.py`, `recommendations.py`, `linking.py`, `notices.py`, `alerts.py`, `reports.py`), `tests/product/`, `data/scripts/make_seed_traces.py` |
| Frontend and other | `slides.pptx` | `frontend/` |
| Data | `data/cache/`, `data/reference/`, `data/scenarios/`, `data/models/`, `data/scripts/` (except the two B/shared scripts) | `data/seed/` |
| Endpoints | trace, wallet risk | cases, complaints, reports, freeze notice, alerts, mock NCRP / SAHYOG |
| `requirements.txt` | Own block of lines (engine libraries) | Own block of lines (product libraries) |
| Env vars | `TRONGRID_API_KEY` | `ENGINE_MODE`, `ENGINE_URL`, `VITE_API_BASE` |
| Shared (change only via 11.1 rule 1) | `CONTRACT.md`, `backend/contract/`, `backend/main.py`, `data/fixtures/`, `data/scripts/gen_fixtures.py`, `backend/paths.py` | same |
| Workload | about 18.5 hrs | about 17.5 hrs |
| Difficulty | High: graph algorithms, heuristics, ML | Medium: UI, templates, glue |
| Main risk | Logic bugs, API limits | Time lost on visual polish |

### 11.3 Kickoff (together, Day 1, hr 0-1)

The only shared work.

- Create the repo with the structure from section 5. Create branches `engine` and `product`.
- Add `CONTRACT.md` and `backend/contract/schemas.py`, and `data/fixtures/trace_hero.json`: the hand-written hero response (11 nodes: 3 victims → reported wallet → 2 pass-throughs → deposit address → exchange hot wallet, plus a mixer, a bridge and an Ethereum wallet with idle funds) that matches the contract.
- Write `backend/main.py` once: the `/api/health` route and every contract route on fixtures (already done in the contract pack). The engine stub in `engine/__init__.py` returns the hero example. `main.py` is B's file (routes); A never edits it, and the seam in `engine/__init__.py` is A's.
- `requirements.txt` is the pinned list from the contract pack. After that, each person adds lines only under their own comment block.
- Agree the constants: hero wallet address, hero complaint ID, backend port 8000, frontend port 5173.
- **Done when:** the server starts, `/docs` loads, and the hero example matches the contract.

### 11.4 Person A: Engine, in order

| # | Task | Step | Time | When |
|---|---|---|---|---|
| A1 | Setup and wallet shortlist | 1, 2 | 1 hr | Day 1, hr 1-2 |
| A2 | Chain adapter and cache | 3 | 2 hrs | Day 1, hr 2-4 |
| A3 | Engine data and hero case | 2 | 2 hrs | Day 1, hr 4-6 |
| A4 | Tracing engine | 4 | 3 hrs | Day 1, hr 6-9 |
| A5 | Attribution and real trace endpoint | 5 | 3 hrs | Day 1, hr 9-12 |
| A6 | Risk and typology | 6 | 2.5 hrs | Day 2, hr 0:30-3 |
| A7 | Hardening and second case | none | 3 hrs | Day 2, hr 3-6 |
| A8 | Slides and talk track | 10 | 2 hrs | Day 2, hr 6-8 |

A2 comes before A3 on purpose: the adapter defines the cache format, and the scripted hero data has to match it.

**A1. Setup and wallet shortlist**
- Create the venv (`python3.12 -m venv env`), then `pip install -r requirements.txt` (the engine libraries `scikit-learn xgboost shap pytest` are already listed; add `requests` or switch `data/scripts/scamWallet.py` to `httpx`).
- Create a free TronGrid key, store it in `.env` as `TRONGRID_API_KEY`, and confirm it with one request.
- Shortlist 3 real TRON scam/laundering wallets from public sources (e.g., flagged addresses on Tronscan). Record the source of each in `data/cache/SOURCES.md`.
- *Done when:* the server runs, `/docs` loads, the key returns data, and 3 wallets with sources are listed.

**A2. Chain adapter and cache** (`backend/engine/chains/tron.py`)
- Call TronGrid as in Step 3. Normalize to `Transfer(tx_hash, from, to, amount, timestamp)`, using the contract's units (epoch seconds, float token amounts). Do all conversion here so B never has to.
- Cache first, then live, and save live results to `data/cache/`. Support a cache-only option that never calls the network.
- Address-format detection (TRON `T…`, Ethereum `0x…`, Bitcoin `1/3/bc1…`). Only TRON is implemented; others return "unsupported".
- Run it on the 3 shortlisted wallets to fill the cache.
- *Done when:* a `pytest` test of the normalization passes on a cached response, and the 3 wallets load with the network switched off.

**A3. Engine data and hero case**
- `data/reference/labels.csv` (`address, chain, entity, type, source`): 4-5 major exchanges' known hot wallets and 1-2 mixer/bridge addresses. Every row has a source.
- `data/reference/vasp_contacts.csv`: one mock nodal contact per exchange. Attribution needs it for the Nearest VASP result.
- **Hero case, fully scripted:** synthetic data in TronGrid format in `data/cache/` for the agreed hero wallet. Scam wallet → 2-3 pass-through wallets (each forwards ≥90% within an hour) → a deposit address that receives from several unrelated wallets and sweeps to a labeled exchange hot wallet. Add that hot wallet to `labels.csv`.
- *Done when:* the hero wallet loads through the adapter and the sweep pattern is visible in the cached data.

**A4. Tracing engine** (`backend/engine/trace/tracing.py`, Step 4 as written)
- Best-first search, stop rules, pass-through detection, idle-funds check.
- Output the graph in the contract format (`TraceResponse`, section 7 step 4 for field rules). Risk fields use fixed placeholder values until A6 (the reported wallet has `risk: null`), so the output is already valid.
- *Done when:* running the tracer on the hero wallet prints a graph that matches the contract and stops at the exchange. **Optional early peek:** merge to `main` now and tell B; B can switch to `http` mode and see real graphs.

**A5b. Live-monitoring seam** (`backend/engine/__init__.py`)
- Add `new_transfers(addresses, since_ts) -> list[Transfer]`: outgoing transfers of the given wallets newer than `since_ts` (live with a TronGrid key, cache otherwise). It must pass through the contract change process because the seam signatures are otherwise fixed. The demo replay (`release_replay`, `data/scenarios/replay_movements.json`) is delivered through it once.
- *Done when:* a replayed movement is returned once, and a re-trace afterwards sees it.

**A5. Attribution and real trace endpoint** (`backend/engine/trace/attribution.py`, `backend/engine/__init__.py`, Step 5 as written)
- Direct match, sweep heuristic, confidence score. Heuristic-only results stay below 90% and are tagged `heuristic`.
- Build the Nearest VASP result, including the transaction path and the nodal contact. Return an empty result when no exchange is found.
- Replace the stub in `engine/__init__.py` (`trace_complaint`) with the real trace (keep the signature and return type). The contract defines no error or cache-only fields yet; if needed (e.g. an optional `cache_only` on `TraceRequest`), add them through 11.1 rule 1.
- *Done when:* the trace endpoint returns a valid response for the hero wallet with a Nearest VASP result (confidence about 0.8-0.9, `heuristic`). This is the end-of-Day-1 acceptance test.

**A6. Risk and typology** (`backend/engine/model/risk.py`)
- **Rule-based first (about 1 hr):** Step 6 features turned into a score, mapped to Low/Medium/High/Critical, plus the typology signatures. Score downstream wallets only; the reported wallet keeps `risk: null`.
- **Then XGBoost (about 1.5 hrs):** train on synthetic + seed wallets behind the same scoring function (model saved to `data/models/risk_model.pkl`), and use SHAP top-3 as the reasons. If time is short, ship the rule-based version only.
- Replace the placeholders from A4 and add the wallet-risk endpoint.
- *Done when:* the hero's pass-through wallets are High/Critical with at least 2 readable reasons, the exchange hot wallet is Low, the reported wallet has `risk: null`, and the contract check passes.

**A7. Hardening and second case**
- One more end-to-end case from a real cached wallet (this exercises the direct label match).
- Edge cases: no exchange found, cycles, empty wallet, mixer or bridge as terminal node, invalid address, TronGrid rate limit (fall back to cache), wallet not in cache.
- `pytest`: hero and real cases match the contract; a cached trace finishes in about 5 seconds or less.
- Optional: an EVM stub adapter returning seeded transfers, and one seeded bridge example (the cross-chain row in section 4).
- *Done when:* all of the above pass.

**A8. Slides and talk track** (`slides.pptx`)
- 5-6 slides built from the demo script (section 8) and the honesty list (section 9): problem, what it is and isn't, how it works, demo, limits, next steps.
- *Done when:* the slides match the 5-minute script.

Then: Checkpoint 2, buffer, and rehearsal (11.6).

### 11.5 Person B: Product, in order

| # | Task | Step | Time | When |
|---|---|---|---|---|
| B1 | Frontend scaffold | 1, 9 | 1 hr | Day 1, hr 1-2 |
| B2 | Case View on the fixture | 9 | 3 hrs | Day 1, hr 2-5 |
| B3 | Seed cases, database, cases API, New Complaint | 2, 9 | 3 hrs | Day 1, hr 5-8 |
| B4 | Recommendations and freeze notice | 7 | 2 hrs | Day 1, hr 8-10 |
| B5 | PDF evidence report | 7 | 2 hrs | Day 1, hr 10-12 |
| B6 | Alerts and mock integrations | 8 | 1.5 hrs | Day 2, hr 0:30-2 |
| B7 | Dashboard and Network View | 9 | 3 hrs | Day 2, hr 2-5 |
| B8 | Animation, Demo Mode, polish | 9, 10 | 2 hrs | Day 2, hr 5-7 |

**B1. Frontend scaffold** (`frontend/`)
- Vite + React + Tailwind, with Cytoscape.js, Recharts and a router. add the product libraries (`reportlab matplotlib`) to your block in `requirements.txt` and run `pip install -r requirements.txt`.
- Four routes: Dashboard, New Complaint, Case View, Network View. Dark theme, a color legend for node types (victim, scam wallet, intermediary, bridge, mixer, exchange), and an API client that reads `VITE_API_BASE`.
- *Done when:* all four routes load and Case View shows the hero example from the kickoff stub.

**B2. Case View on the fixture**
- Cytoscape graph: color by node type, edge thickness by amount, click a node for a side panel (risk, reasons, typology, idle balance, transactions).
- **Nearest VASP card:** exchange, deposit address, hops, amount, time, confidence, method tag, evidence list, contact. Include an empty state for "no exchange reached".
- Urgency badge with its reasons (case level), and a `LIVE` / `CACHED` / `SIMULATED` badge.
- *Done when:* Case View is complete against the hero example, and the empty state works on an edited copy.

**B3. Seed cases, database, cases API, New Complaint** (`backend/`, `data/`)
- `data/seed/seed_cases.json`: 8-10 complaints (complaint ID, wallet, amount, fraud type, state) with **synthetic** addresses.
- `data/scripts/make_seed_traces.py` generates one pre-built trace per case into `data/seed/seed_traces.json`, checked against the contract. Include: 2-3 groups of cases sharing a downstream wallet, 2 isolated cases, different exchanges, one mixer-terminal, one bridge-terminal, one case with idle funds, one with no exchange found, and realistic elapsed times for the dashboard.
- `product/store.py` (SQLite) loads the seeds at startup. `engine_client.py` implements `fixture` and `http` modes (11.1).
- Endpoints: submit a complaint (stores it, calls the engine, stores the result), list cases, get one case.
- New Complaint page submits and opens the Case View. Add a "Fill hero example" button that prefills the agreed hero wallet; the demo starts there.
- *Done when:* in `fixture` mode, submitting the hero complaint stores a case and Case View renders it, and the case list shows the seeded cases plus the new one.

**B4. Recommendations and freeze notice** (`backend/product/recommendations.py`, `backend/product/reports.py`)
- Rules, using only the trace data: idle funds → "act immediately"; VASP found at or above the confidence threshold → "issue freeze/KYC request to X"; mixer reached → "preserve evidence, monitor exits"; bridge reached → "continue on destination chain". Shown in a panel on Case View.
- **Case urgency:** `act_now | act_soon | preserve` plus `urgency_reasons[]`, using the first-match-wins rules in Step 7 (placeholder thresholds). Shown as a badge on Case View and as a column in the case list.
- **Freeze notice:** a template filled with complaint ID, the transaction path, addresses, amounts and times. It requests a freeze **plus** preservation of KYC, bank, phone and IP data. Legal-section references stay as placeholders. Add the endpoint and a Download button.
- *Done when:* the hero case shows `act_now` with its reasons, at least 2 recommendations, and downloads a filled notice.

**B5. PDF evidence report** (`backend/product/reports.py`)
- ReportLab: summary, graph image (drawn from the trace with networkx + matplotlib), transaction table, attribution evidence, methodology and limitations, SHA-256 hash of the report.
- Add the endpoint and a Download Report button.
- *Done when:* the PDF opens correctly for the hero case and one seeded case, and the hash is printed.

**B6. Alerts and mock integrations** (`backend/product/alerts.py`, `backend/main.py`)
- **Watcher:** poll the watchlist (leaf and idle wallets) every 30 s through `engine_client.new_transfers`; on a new transfer re-trace, re-run attribution and urgency, update `urgency_as_of`, push an alert; always refresh `monitoring` after a successful check.
- SSE alert stream, including `URGENCY_CHANGED`. A "Simulate fund movement" button on Case View releases a recorded replay (SIMULATED) for the open case and re-checks it at once.
- Mock NCRP endpoint: maps an NCRP-style payload to an engine request, runs it through `engine_client`, stores the case. Mock SAHYOG endpoint: accepts the freeze notice and returns an acknowledgment.
- Export the OpenAPI spec as the integration document.
- *Done when:* clicking Simulate shows the events in the UI and the urgency badge changes (Act now to Act soon for the idle-funds scenario), and a `curl` with an NCRP payload creates a case.

**B7. Dashboard and Network View**
- **Dashboard (Recharts):** KPI tiles (cases, total amount traced, average time-to-attribution, % with VASP identified), cases by fraud type, top receiving exchanges, and a live alert feed.
- **Network View:** build one graph over all stored case graphs, find groups with `networkx.connected_components`, and render each group with Cytoscape. Clicking a group lists its complaints.
- *Done when:* the dashboard shows numbers computed from the seeded cases and the Network View shows at least one group of 3 or more complaints.

**B8. Animation, Demo Mode, polish**
- Short hop-by-hop animation as the trace builds (reveal edges in time order).
- **Demo Mode** toggle in the top bar: asks the engine for cached data only. Show a clear message when a wallet is not cached.
- Run the 5-minute script (section 8) from a clean start with Demo Mode on and the network switched off, and fix whatever breaks.
- *Done when:* the full script runs with no manual workarounds.

Then: Checkpoint 2, buffer, and rehearsal (11.6).

### 11.6 Sync points and the combined timeline

| When | Person A | Person B | Sync |
|---|---|---|---|
| Day 1, hr 0-1 | Kickoff | Kickoff | **Together** (11.3) |
| Day 1, hr 1-9 | A1, A2, A3, A4 | B1, B2, B3 | None. Optional: A merges A4 at hr 9 so B can try real graphs |
| Day 1, hr 9-12 | A5 | B4, B5 | None. A5's done-when is the end-of-Day-1 acceptance test |
| Day 2, hr 0-0:30 | Integration | Integration | **Checkpoint 1:** B switches to `http` mode, runs the hero complaint through the real engine, and both fix any mismatch |
| Day 2, hr 0:30-8 | A6, A7, A8 | B6, B7, B8 | None |
| Day 2, hr 8-8:30 | Run the script | Run the script | **Checkpoint 2:** full demo script (section 8) once, end to end, Demo Mode on |
| Day 2, hr 8:30-9 | Fix A-side bugs | Fix B-side bugs | Buffer |
| Day 2, hr 9-12 | Rehearse | Rehearse | **Together:** 3 timed run-throughs and a backup screen recording |

### 11.7 Handoff rules

- **If A falls behind,** B keeps going on fixtures. The hero case still runs end to end in `fixture` mode, and Demo Mode exists for exactly this.
- **If B falls behind,** B cuts per 11.8. A can take over a whole task only if B hands it over in writing and the file moves to A's ownership (for example the PDF report). Two people never edit the same file.
- **If either finishes early:** A adds more cached real cases and labels. B adds more seed cases and polish. Neither starts work in the other's folders.

### 11.8 Cut order for each person

Follows the global order in section 10 (Network View → alerts → ML model → live TRON trace).

- **A cuts, in order:** EVM stub → XGBoost (keep the rule-based score) → live TronGrid calls (keep cache). **Never cut:** tracing, attribution, the hero case.
- **B cuts, in order:** animation → Network View → alerts → dashboard charts. **Never cut:** the Case View graph, the Nearest VASP card, the freeze notice and PDF report.

---

## 12. Progress Log (status of the work moved into place)

Contract rules live in `CONTRACT.md`. Endpoints are under `/api/...` and the contract is `backend/contract/schemas.py`.

| Item | Status | Location |
|---|---|---|
| Kickoff: contract models, all `/api` routes (fixture-backed), engine stub returning the hero example | DONE | `backend/contract/`, `backend/main.py`, `backend/engine/__init__.py` |
| Contract tests (4 passing: graph shape, Nearest VASP in graph, idle funds, wallet risk) | DONE | `backend/tests/contract/test_contract.py` |
| Hero example + fixtures for every endpoint | DONE | `data/fixtures/` (`trace_hero.json` is the hero) |
| Product routes (cases, freeze notice, report, dashboard, networks, alerts SSE, NCRP/SAHYOG mocks) | STUB DONE | `backend/main.py` (TODO(B): real implementations, B3-B8) |
| Step 1: repo, structure, venv (`env/`, Python 3.12, all libraries installed), contract and `/api/health` route | DONE | `env/`, `requirements.txt`, `backend/` |
| Step 1: TronGrid key in `.env` | DONE (key to paste) | `.env.example` committed; local `.env` created (git-ignored). `TRONGRID_API_KEY` is still empty: paste a free key from trongrid.io. The adapter works without one, rate-limited |
| Step 1 / B1: frontend scaffold | DONE (branch `product`) | `App.jsx`, 4 routes, dark theme, `lib/api.js`, `lib/colors.js`, badges, legend; `vite build` passes. B2 Case View is also done there |
| Step 2 / A3: `labels.csv` | DONE | `data/reference/labels.csv` (`address, chain, entity, type, source, note`): fictional hero/seed rows (Example Exchange A/B/C hot wallets, Example Bridge x2, Example Mixer), 3 real hot wallets with an on-chain activity check, 1 DEX pool (`swap`), Tornado Cash router. `chain`/`type` match the contract. 3 rows that did not behave like hot wallets were removed; see `data/reference/LABELS.md`. Still no *real* labeled TRON bridge/mixer |
| Step 2 / A3: `vasp_contacts.csv` | DONE | `data/reference/vasp_contacts.csv` (`vasp, nodal_officer, designation, email, phone`): mock contacts for Example Exchange A/B/C (matching the fixtures) and the 5 real-named exchanges |
| Step 2 / A1: 3 real scam wallets cached | DONE | `data/scripts/scamWallet.py` picks the most recent Tether-blacklisted (`AddedBlackList`) TRON wallets with a usable history and caches their USDT-TRC20 transfers plus their biggest next-hop recipients in `data/cache/tron/`. Raw events are in `data/cache/blacklist_events/`, provenance in `data/cache/SOURCES.md` |
| Step 2 / A3: hero case | DONE | `data/scripts/make_hero_cache.py` writes C-001 in TronGrid format from `trace_hero.json` (same tx hashes, amounts, times). The deposit address has 14 unrelated senders, all swept to the labeled Example Exchange A hot wallet. Bridge exit leg in `data/cache/bridge_legs.json` |
| Step 2 / B3: `seed_cases.json` + `seed_traces.json` | DONE (branch `product`) | `data/scripts/make_seed_traces.py` writes one trace per seed case: NET-1/NET-2 share deposit addresses, plus mixer-terminal, bridge-terminal, idle-funds and no-exchange cases. Checked by `tests/product/test_product.py` |
| Step 3 / A2: chain adapter | DONE | `backend/engine/chains/tron.py`: `Transfer` normalization (seconds, token-unit floats), cache first then live then save, fingerprint paging, 429 retry, `TRONGRID_API_KEY` from `.env`, `detect_chain()` for tron/ethereum/bitcoin/solana, CLI to refill the cache. `tests/engine/test_tron.py` (18 tests, offline) |
| B3: `store.py`, `engine_client.py`, cases API, New Complaint | DONE | `backend/product/store.py` (SQLite, seeds the 8 cases), `engine_client.py` (fixture / engine / http modes), cases routes in `main.py`, `frontend/src/pages/NewComplaint.jsx`; tests in `tests/product/test_product.py` |
| Step 4 / A4: tracing engine | DONE | `backend/engine/trace/tracing.py`: best-first search, stops at labeled exchange/bridge/mixer, depth 5 and flows under 1%; pass-through (`intermediary`) at >=90% within 1 hour; idle balance for leaf nodes (computed from cached transfers); `build_response()` with placeholder risk and no `nearest_vasp`. Wired into `engine.trace_complaint` (`TRACING=fixture` restores the old stub). CLI: `cd backend && python -m engine.trace.tracing <wallet> [amount]`. `tests/engine/test_tracing.py` (15 tests, offline). Hero trace reaches Example Exchange A at hop 3 |
| Step 5 / A5: attribution + real trace endpoint | DONE | `backend/engine/trace/attribution.py`: sweep heuristic (>=5 senders, >=90% forwarded to a labeled hot wallet, `heuristic`, capped 0.89) and direct label match (`deterministic`, 0.95); weighted confidence; contact from `vasp_contacts.csv`; retypes the deposit node to `exchange`. `engine.trace_complaint` now returns graph + `nearest_vasp` + measured `time_to_attribution_sec`. `tests/engine/test_attribution.py` (12 tests). Hero: Example Exchange A, deposit `TAD47A…`, hops 2, 7,850 USDT, confidence 0.87 |
| Contract v1.1.0: reported wallet unscored, case urgency | DONE | `backend/contract/schemas.py` (`CONTRACT_VERSION` 1.1.0: nullable `risk`/`risk_score`, `urgency`, `urgency_reasons`), `data/scripts/gen_fixtures.py`, `data/scripts/make_seed_traces.py`, `data/fixtures/`, `data/seed_*.json` regenerated. `tracing.py` labels hop 0 `Reported` with `risk: null`. B4 urgency in `recommendations.build_urgency` (first match wins, placeholder thresholds), stored on the case by `store.py`; UI shows an urgency badge with reasons (Case View, case list) and a `Reported` badge in the node panel. `tests/product/test_urgency.py` (7 tests) |
| Live monitoring and urgency "as of" (the live-monitoring proposal) | DONE | Contract v1.1.0 adds `urgency_as_of`, `monitoring` (`live/stale/off`, `last_checked_at`, `poll_interval_sec`) and alert type `URGENCY_CHANGED`. Engine seam `new_transfers(addresses, since_ts)` plus the demo replay (`data/scenarios/replay_movements.json`, SIMULATED). The `act_now` 24-hour trigger is now "fresh outgoing transfer in the last 15 minutes". B: `backend/product/alerts.py` watcher (30 s poll, SSE, re-trace on movement, stale when a check fails), `POST /api/cases/{id}/simulate-movement`, `store.reevaluate`. UI: urgency "as of" time, live/stale indicator and warning, Simulate fund movement button, per-case alert list. `tests/product/test_monitoring.py` (11 tests); demo with the `idle` scenario wallet |
| Project reorganised into folders | DONE | `backend/engine/` (seam in `__init__.py`, `chains/`, `trace/`, future `model/`), `backend/product/` (B), `backend/paths.py` for every data path, tests in `tests/{contract,engine,product}`, `data/{reference,seed,scenarios,scripts,...}`, frontend `components/{common,case}`, `docs/archive/`. Imports are now `engine.trace.tracing`, `product.store`, etc.; run `pytest` from the repo root or `backend/` (`pytest.ini`) |
| Step 6 / A6: risk and typology | DONE | `backend/engine/model/`: `features.py` (7 features), `rules.py` (rule score, the fallback), `synthetic.py` + `train.py` (XGBoost, `data/models/risk_model.pkl`), `scoring.py` (level, SHAP reasons, thin and truncated history caps), `typology.py` (signature rules), `battery.py` / `typology_battery.py` (DEV and one-shot HOLDOUT scenario batteries), `risk.py` (scores onto the graph; wired into `trace_complaint`). Reported wallet stays `risk: null` and carries the typology; labeled exchange/bridge/mixer use fixed values. `engine.wallet_risk` (the standalone `GET /api/wallets/{address}/risk`) scores any TRON address from its own transfers; labeled endpoints use the fixed values; unscorable addresses are Low with a reason. The A6 done-when holds: the hero pass-through wallets are Critical with 2+ reasons, the exchange wallets are Low, the reported wallet has `risk: null`, the contract check passes. The model is trained on synthetic data |
| B5: PDF evidence report | DONE | `backend/product/reports.py`: summary, fund-flow graph image, transaction table, attribution evidence, wallet risk, recommendations, methodology and limits; every page footer carries a SHA-256 of the case data; `GET /api/cases/{id}/report` and the Download Report button |
| B6: alerts and mock integrations | DONE | `backend/product/alerts.py` (watcher, SSE, scripted case-aware alerts in fixture mode, NEW_COMPLAINT_LINKED and HIGH_RISK_WALLET on new cases), `integrations.py` (NCRP creates a case and alerts; SAHYOG moves a case to `notice_sent`), `docs/openapi.json` via `python -m product.export_openapi`; UI: `AlertFeed`, `Toasts`, `useAlerts` |
| B7: dashboard and Network View | DONE | `backend/product/analytics.py` computes `/api/dashboard` and `/api/networks` from the case store; UI: KPI tiles, breakdown bars by fraud type / exchange / state, recent cases, Network View with a graph per linked group |
| B8: animation, Demo Mode, polish | PARTLY DONE | hop-by-hop trace animation is done (`TraceGraph.jsx`); the Demo Mode toggle is still disabled in the sidebar; the full 5-minute script has not been run end to end from a clean start |
| A7: hardening and a second case | DONE | A7.1 `FetchError` with reasons for TronGrid failures, a 40-wallet and 30-second budget per trace, case notes saying how complete a trace is; A7.2 edge cases through the whole pipeline (self-transfers, duplicates, idle funds at the reported wallet, follow only what left after the victim paid, notes for exchange/mixer/bridge/invalid/uncached wallets, exchange tie-break); A7.3 `tests/engine/test_pipeline_contract.py` checks every cached wallet, the scenarios, a stress trace and the API against the contract and a 5 s limit; A7.4 a REAL flow to a labeled exchange (`data/scripts/make_real_case.py`, `data/scenarios/real_case.json`, 7 real wallets; Binance by the sweep rule at 0.68, and a direct label match when reported from the deposit address; the reported wallet is not claimed to be fraud); A7.5 the trace follows money across the bridge onto a seeded, SIMULATED Ethereum side (`engine/chains/evm_stub.py`, `data/cache/evm/`, `bridge_legs.json`), so the live hero trace now finds the 3,720 USDT idle and is `act_now` like the fixture |
| A8 | NOT STARTED | slides |

**Audit of Steps 1-3 (updated 2026-10-20).** Steps 1-3 are complete: the contract, routes and tests work, the cache holds 3 real flagged wallets (with next hops) and the scripted hero case, `labels.csv`/`vasp_contacts.csv` are aligned with the contract, and `backend/engine/chains/tron.py` is the adapter. Open items: paste a TronGrid key into `.env`; find a real, verifiable TRON bridge or mixer label. `engine` + `product` are merged into `main`; Step 4 (tracing) is done. Step 5 (attribution) and contract v1.1.0 (reported wallet unscored, case urgency) are done. Next: A6 risk and typology (`backend/engine/model/risk.py`).

**Reconciliation notes.** The contract pack's layout won where it differed from section 5: the contract is a package (`contract/schemas.py`, not `contract.py`), the hero example is `data/fixtures/trace_hero.json`, the engine seam is `engine/__init__.py`, and `main.py` holds all routes as CONTRACT.md lists. The `routes_engine.py` / `routes_product.py` split was tried and dropped after merging `origin/main`; the API surface was identical. DEMO.md sections 6-11 were then aligned with CONTRACT.md: `/api` endpoint paths, epoch-second timestamps, the seven node types, `deterministic`/`heuristic` methods, the `live/cached/simulated` source badge, typology and alert enums, the contract change process, and `main.py` owned by B with `engine/__init__.py` as the A/B seam. Run: `pip install -r requirements.txt`, then `cd backend && uvicorn main:app --reload --port 8000`.