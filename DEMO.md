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
4. Wallets get a risk level, fraud type, and reason codes (AI).
5. A freeze request and PDF evidence report are generated.
6. A live alert fires when funds move.
7. A dashboard shows cases and a linked criminal network.

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
| Risk categorization | Low/Medium/High/Critical + SHAP reasons | **Real model**, trained on synthetic + seed data |
| Fraud typology | Investment / sextortion / ransomware / phishing | Rule-assisted ML |
| Automated alerts | Live alert via SSE | Simulated trigger |
| SAHYOG / NCRP integration | Mock connectors + API spec | Simulated |
| Investigative recommendations | Rule-based action list | **Real** |
| Fund-flow visualization | Interactive graph | **Real** |
| Analytics dashboard | KPIs, charts, network view | Seeded data |
| Standardized reports | PDF evidence report + freeze notice | **Real** |
| Multi-chain support | Adapter interface, TRON + one EVM stub | TRON real, EVM seeded |

---

## 5. Project Structure

```
chaintrace/
├── backend/
│   ├── main.py                 # FastAPI app + routes
│   ├── chains/tron.py          # TronGrid adapter + cache
│   ├── tracing.py              # forward trace + pass-through
│   ├── attribution.py          # labels, sweep heuristic, confidence
│   ├── risk.py                 # features, model, SHAP
│   ├── reports.py              # PDF + freeze notice
│   ├── alerts.py               # SSE alert stream
│   └── db.py
├── data/
│   ├── labels.csv              # exchanges, mixers, bridges
│   ├── vasp_contacts.csv       # mock nodal contacts
│   ├── cache/                  # saved TronGrid responses
│   └── seed_cases.json         # 8-10 demo complaints
├── frontend/                   # React + Tailwind + Cytoscape
└── DEMO.md
```

---

## 6. Day 1: Engine (Backend + Data)

### Step 1. Project setup (1 hr)
**What:** Repo, environment, folder structure, API keys.
**How:**
- `python -m venv .venv`, then `pip install fastapi uvicorn httpx networkx pandas scikit-learn xgboost shap reportlab`.
- Create a free TronGrid API key and store it in `.env`.
- Start FastAPI with a `/health` route and confirm `/docs` loads.

### Step 2. Seed data (2 hrs)
**What:** The data that makes the demo reliable.
**How:**
- Pick **3 real TRON scam/laundering wallets** from public sources (e.g., publicly flagged addresses on Tronscan) and save their TronGrid responses into `data/cache/`.
- Build `labels.csv` with columns `address, chain, entity, type, source`. Include 4-5 major exchanges' known hot wallets, 1-2 mixer/bridge addresses, and note the source of every label.
- Create `seed_cases.json` with 8-10 complaints (complaint ID, wallet, amount, fraud type, state). Some should share a downstream wallet so the network feature has something to find.
- Create one **fully scripted case** where the trace clearly ends at an exchange; this is your hero demo.

### Step 3. Chain adapter (2 hrs)
**What:** Fetch and normalize transactions.
**How:**
- Call TronGrid: `GET /v1/accounts/{addr}/transactions/trc20?contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t&limit=200` (USDT-TRC20; 6 decimals; timestamps in ms).
- Normalize to `Transfer(tx_hash, from, to, amount, timestamp)`.
- Always try the cache first; fall back to live; save live results to the cache.
- Add address-format detection (TRON `T…`, Ethereum `0x…`, Bitcoin `1/3/bc1…`) to show multi-chain routing, even if only TRON is fully implemented.

### Step 4. Tracing engine (3 hrs)
**What:** Follow money forward and stop at meaningful endpoints.
**How:**
- Best-first search: a priority queue ordered by value and recency, starting from the reported wallet.
- Add each outgoing transfer as a graph edge. Stop expanding at: known exchange, mixer, bridge, depth 5, or flows under 1% of the case value.
- **Pass-through detection:** tag a wallet `intermediary` if it forwards ≥90% of what it receives within ~1 hour.
- Check balances of leaf nodes; a leaf still holding funds gets an "idle funds" flag.
- Output a graph as JSON: nodes (address, type, label) and edges (tx, amount, time).

### Step 5. Attribution engine (3 hrs)
**What:** Name the exchange and score the confidence.
**How:**
- **Direct match:** destination address found in `labels.csv`.
- **Sweep heuristic:** if a candidate deposit address receives from many unrelated wallets and forwards its balance to a labeled hot wallet, attribute it to that exchange.
- **Confidence score:** weighted sum of `label_match`, `sweep_count`, `counterparty_diversity`. Cap heuristic-only results below 90% and tag them `heuristic`.
- Return a "Nearest VASP" object: exchange, deposit address, hops, amount, time, confidence, evidence list, nodal contact from `vasp_contacts.csv`.

**End of Day 1 checkpoint:** `POST /trace` with a wallet returns a graph plus a Nearest VASP result for the hero case.

---

## 7. Day 2: AI, Outputs, Interface

### Step 6. AI risk and typology (2.5 hrs)
**What:** Risk level, fraud type, reason codes.
**How:**
- **Features per wallet:** age, tx count, in/out ratio, median time-to-forward, unique senders, round-number ratio, fan-in degree.
- **Training data:** generate a synthetic labeled set (scam collectors vs normal vs exchange-like) using realistic ranges, plus your seed wallets. Be upfront in the UI and slides that the model is trained on synthetic + seed data for the demo.
- Train XGBoost; map probability to Low/Medium/High/Critical; compute SHAP top-3 reasons ("forwards funds in 4 minutes", "89 unique senders").
- **Typology:** rule-assisted classifier using signatures: many small deposits + fast consolidation → investment/task scam; many unique tiny senders → sextortion; few large payments + mixer → ransomware.
- Expose `GET /wallets/{addr}/risk`.

### Step 7. Reports and recommendations (2 hrs)
**What:** Turn findings into actions.
**How:**
- **Recommendation rules:** idle funds found → "act immediately"; VASP found ≥ threshold → "issue freeze/KYC request to X"; mixer reached → "preserve evidence, monitor exits"; bridge reached → "continue on destination chain".
- **Freeze notice:** text template filled with complaint ID, tx hashes, addresses, amounts, times; request freeze **plus** preservation of KYC, bank, phone and IP data. Leave legal-section references as placeholders.
- **PDF evidence report (ReportLab):** summary, graph image, transaction table, attribution evidence, methodology and limitations, SHA-256 hash of the report.

### Step 8. Alerts and mock integrations (1.5 hrs)
**What:** Real-time feel and integration story.
**How:**
- `GET /alerts/stream` using SSE. A "Simulate fund movement" button (or a background replay of a recorded transaction) pushes an alert like `FUNDS_MOVED` or `REACHED_VASP`.
- `POST /integrations/ncrp/complaints`: accepts the NCRP-style payload and starts a trace. `POST /integrations/sahyog/notice`: accepts the freeze notice and returns a mock acknowledgment.
- Export the OpenAPI spec as the integration contract.

### Step 9. Frontend (5 hrs)
**What:** The part judges see.
**How:**
- **Pages:** (1) Dashboard, (2) New Complaint, (3) Case View, (4) Network View.
- **Case View:** Cytoscape graph with colors by node type (victim, scam wallet, intermediary, bridge, mixer, exchange); edge thickness = amount; click a node for risk, reasons and transactions. Add a "Nearest VASP" card, a risk badge, a recommendations panel, and **Download Report / Freeze Notice** buttons.
- **Dashboard (Recharts):** KPI tiles (cases, total amount traced, average time-to-attribution, % with VASP identified), cases by fraud type, top receiving exchanges, a live alert feed.
- **Network View:** group seed complaints that share downstream wallets into one network graph (use `networkx.connected_components`).
- Use a dark theme, a consistent color legend, and a short animation as the trace builds hop by hop; it makes the speed visible.

### Step 10. Polish and rehearsal (2 hrs)
**What:** A demo that cannot fail.
**How:**
- Add an "Demo Mode" toggle that forces cached data.
- Mark each result as `LIVE` or `SIMULATED`.
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
| 2:45 | Show risk badge, fraud type, SHAP reasons | "AI prioritizes; evidence stays explainable." |
| 3:15 | Generate freeze notice + PDF report | "Ready to send in one click." |
| 3:45 | Trigger a live alert | "If funds move, we know." |
| 4:15 | Open the Network View | "40 complaints, one organized network." |
| 4:45 | State limits and what's next | "Attribution and leads, not a magic recovery tool." |

---

## 9. What to Be Honest About in the Demo

- Label database is small; real deployment needs a much larger one.
- Risk model is trained on synthetic + seed data for the demo.
- NCRP/SAHYOG links are simulated.
- The tool finds the exchange; the exchange's KYC data links to people and the fiat/mule layer.
- Mixers and privacy tools are flagged, not "solved".

---

## 10. Priority if Time Runs Short

Cut in this order (last items first): Network View → alerts → ML model (fallback to rule-based scoring) → live TRON trace. **Never cut:** graph, Nearest VASP card, freeze notice/report.
