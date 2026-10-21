# ChainTrace

A real-time crypto fraud attribution tool for cybercrime investigators. Give it a wallet from a fraud complaint and it follows the stolen USDT forward, draws the fund flow, names the exchange that received the money, ranks how urgent the case is, drafts the freeze request, and keeps watching the wallets that still hold funds.

> **Everything in the demo data is fictional unless stated.** Names like "Example Exchange A", the hero wallet and the seeded cases are made up. The cache also holds three real wallets that Tether froze; see [Data and its honesty limits](#9-data-and-its-honesty-limits).

---

## Index

1. [Background: the problem](#1-background-the-problem)
2. [The product](#2-the-product)
3. [Our solution](#3-our-solution)
4. [Set up the project on your device](#4-set-up-the-project-on-your-device)
5. [The backend](#5-the-backend)
6. [The frontend](#6-the-frontend)
7. [The risk model: features, selection, training](#7-the-risk-model-features-selection-training)
8. [How to read the website](#8-how-to-read-the-website)
9. [Data and its honesty limits](#9-data-and-its-honesty-limits)
10. [Tests](#10-tests)
11. [Project status and further reading](#11-project-status-and-further-reading)

---

## 1. Background: the problem

Victims of cyber-fraud in India report the crypto wallet addresses they paid on the national cybercrime portal (NCRP) and the 1930 helpline. Fraudsters do not keep the money in that wallet. Within minutes they move it through a chain of burner wallets, swap it across chains, run it through bridges and mixers, and finally cash it out at an exchange.

Manual tracing takes days. By the time an investigator knows which exchange received the money, the exchange has often already paid it out, so the freeze request arrives too late.

Three facts shape the whole design:

- **Wallets carry no identity.** A wallet address does not say who owns it. The identity lives at the exchange: crypto is only useful to a fraudster once it is converted to cash, and that conversion point (exchange, P2P, OTC) is where KYC records exist.
- **The exchange is the chokepoint.** If we can say *which exchange received the funds, at which deposit address*, an officer can send that exchange a freeze and KYC request. That request is the useful output.
- **Speed matters more than completeness.** A fast, explainable answer while some money may still be there is worth more than a perfect report a week later.

---

## 2. The product

ChainTrace is an **attribution and lead-generation tool**. It does:

- Start from a complaint (wallet, amount, fraud type, state) and trace the funds forward across several hops.
- Show the fund flow as an interactive graph.
- Name the exchange that received the money, with a confidence score and the evidence behind it.
- Tell the officer how urgent the case is (**Act now / Act soon / Preserve**) and why.
- Draft a freeze-and-KYC notice to the exchange, and recommend next actions.
- Keep watching wallets that still hold money and raise an alert, and re-rank the case, when they move.
- Group complaints that share wallets into one criminal network (the seeded demo cases show this).

It does **not**:

- Recover the money. `Act now` means a freeze may still be possible in this window, not that it will succeed.
- Identify the criminal from the chain alone. The exchange's KYC data is the bridge to real people, bank accounts and UPI mule accounts.
- "Solve" mixers or privacy tools. They are flagged as endpoints with a warning, not traced through.

---

## 3. Our solution

One complaint goes through a pipeline. Each stage is a separate module, and the first four are deterministic, so their output can be explained and defended.

```
complaint ──► 1. Trace ──► 2. Attribute ──► 3. Score risk ──► 4. Rank urgency ──► 5. Act ──► 6. Monitor
 (wallet,       follow       which exchange     how suspicious    Act now / Act      freeze      watch idle
  amount…)      the money    got it?            is each wallet?   soon / Preserve    notice      wallets, alert
```

| Stage | What it does | Where | State |
|---|---|---|---|
| **1. Trace** | Best-first search forward from the reported wallet. Stops at known exchanges, bridges and mixers, at depth 5, and for flows under 1% of the case value. Tags a wallet `intermediary` if it forwards 90% or more of what it receives within about an hour. Flags leaf wallets still holding money as **idle funds**. | `backend/engine/trace/tracing.py` | Done |
| **2. Attribute** | Names the exchange. A **direct match** means the trace reached an address in the label list (`deterministic`, confidence 0.95). The **sweep heuristic** treats a wallet with many different senders that forwards its balance to a labeled hot wallet as a customer deposit address (`heuristic`, confidence capped below 0.90). | `backend/engine/trace/attribution.py` | Done |
| **3. Score risk** | Risk level (Low to Critical), reasons and fraud type for each downstream wallet. The reported wallet is not scored: a victim already named it. | `backend/engine/model/` | Done; see [section 7](#7-the-risk-model-features-selection-training) |
| **4. Rank urgency** | Case-level rule set, first match wins (see [section 8](#82-urgency-the-badge-that-matters-most)). | `backend/product/recommendations.py` | Done |
| **5. Act** | Recommendations panel and a freeze-notice draft built from a template. A PDF evidence report is generated from the stored case. | `backend/product/` | Done (freeze notice, recommendations, PDF report) |
| **6. Monitor** | A watcher polls the leaf and idle wallets every 30 seconds. When one moves it re-traces, re-runs attribution and urgency, updates the "as of" time and pushes an alert. | `backend/product/alerts.py` | Done (demo feed is a recorded replay) |

**Why deterministic first, AI second.** Tracing and attribution are rules and label lookups. That keeps them explainable. AI is used where rules are weakest: scoring how suspicious a wallet looks and classifying the fraud type.

**Design choice: cache first.** The system works with no API key by reading a cache of saved TronGrid responses, so the demo never depends on the network. With a key it can call TronGrid live and save what it gets.

---

## 4. Set up the project on your device

### 4.1 What you need

| Tool | Version | Used for |
|---|---|---|
| Python | **3.12** (the pinned libraries were tested on it) | backend and model |
| Node.js | 18 or newer | frontend |
| Git | any | to clone |
| A TronGrid API key | optional | live blockchain data; free from <https://www.trongrid.io/> |

You do not need a key to run the demo. Without one, the system reads only the cached wallets.

### 4.2 Install

```bash
# 1. get the code
git clone https://github.com/Arjit-Dot/ChainTrace.git
cd ChainTrace

# 2. backend: a virtual environment and the pinned libraries
python3.12 -m venv env
source env/bin/activate            # Windows: env\Scripts\activate
pip install -r requirements.txt

# 3. optional: a TronGrid key
cp .env.example .env               # then paste the key after TRONGRID_API_KEY=

# 4. frontend libraries
cd frontend && npm install && cd ..
```

### 4.3 Run it (two terminals)

```bash
# terminal 1 - backend on :8000  (API docs at http://localhost:8000/docs)
source env/bin/activate
cd backend
ENGINE_MODE=engine uvicorn main:app --reload --port 8000

# terminal 2 - frontend on :5173 (it proxies /api to :8000)
cd frontend
npm run dev
```

Open <http://localhost:5173>. You land on the **gateway**, which stands in for the hand-off from an official government website: the message in the middle over a moving fund-flow graph (nodes drift, links form, payments pulse along them, and the cursor nudges nodes aside; it draws one still frame if your system prefers reduced motion), and a side panel that is open by default and can be collapsed to a slim rail (your choice is remembered) holding the complaint tracker, a link to file, and the officer console. It leads to two sides:

- **Citizens** (`/citizen/...`): file a complaint and track it. No officer navigation.
- **Officers** (`/officer/...`): the console with the dashboard, cases and networks. It opens in a separate browser tab from the gateway. There is no login in this demo.

First thing to try: **File a complaint**, click **Fill demo example** (wallet `TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo`, amount 12000) and submit; then open the **officer console** in the other tab and find the case on the dashboard. (In this version submitting still traces straight away; the officer-triggered trace arrives in a later stage.)

### 4.4 Engine modes

`ENGINE_MODE` chooses where traces come from:

| Mode | What it does |
|---|---|
| `fixture` (default) | Returns pre-built traces. No engine runs. Useful for working on the interface. |
| `engine` | Runs the real tracer, attribution and urgency in-process. Use this for the full demo. |
| `http` | Calls a separate engine at `ENGINE_URL`. |

If the engine fails, the API falls back to the fixture and says so in the case's `notes`, so a demo never shows a blank page.

### 4.5 Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `TRONGRID_API_KEY` | empty | Enables live TronGrid calls. Without it the engine is cache-only. |
| `ENGINE_MODE` | `fixture` | See above. |
| `ENGINE_URL` | `http://localhost:8001` | Engine address for `http` mode. |
| `CHAINTRACE_POLL_SEC` | `30` | How often the watcher polls. |
| `CHAINTRACE_MONITOR` | `1` | `0` turns the watcher off (cases then show monitoring "off"). |
| `CHAINTRACE_DB` | `data/chaintrace.db` | Where the SQLite case store lives. |
| `TRACING` | `real` | `fixture` makes the engine return the hero fixture instead of tracing. |
| `VITE_API_BASE` | empty | Frontend API base URL if the backend is elsewhere. |

### 4.6 Reset or rebuild

- **Fresh case list:** stop the backend and delete `data/chaintrace.db`. Seeded cases come back on the next start; cases you submitted are gone.
- **Rebuild fixtures, seeds and scenarios** (only needed after a contract or data change), from the repo root:

```bash
python data/scripts/gen_fixtures.py                 # one example response per endpoint
cp data/fixtures/cases.json data/seed/seed_cases.json
python data/scripts/make_seed_traces.py             # the 8 seeded traces
python data/scripts/make_attribution_scenarios.py   # the 8 test scenarios + replay feed
```

---

## 5. The backend

A Python 3.12 FastAPI application. It is split into two packages with a clear boundary, plus a shared contract.

```
backend/
  main.py          API routes. Run with: uvicorn main:app
  paths.py         where every data file lives (import paths from here)
  contract/        schemas.py: the API contract as Pydantic models. The single source of truth.
  engine/          FINDS things (traces, attribution, risk)
    __init__.py      the seam: trace_complaint, wallet_risk, new_transfers, replay helpers
    chains/tron.py   TronGrid adapter: normalises transfers, cache first, then live, then save
    trace/           tracing.py (forward trace), attribution.py (which exchange)
    model/           features, rules, trained model, scoring, typology, and risk.py (puts scores on the graph)
  product/         BUILDS from the findings
    engine_client.py how the product reaches the engine (fixture / engine / http)
    store.py         SQLite case store; seeds the 8 demo cases at startup
    recommendations.py   action list and case urgency
    linking.py       groups complaints that share wallets into networks
    notices.py       freeze notice, from a Jinja template in product/templates/
    reports.py       PDF evidence report with a SHA-256 hash of the case data
    analytics.py     dashboard and network figures, computed from the stored cases
    integrations.py  mock NCRP and SAHYOG endpoints (simulated)
    alerts.py        live-monitoring watcher, alert stream, scripted demo alerts
    export_openapi.py  writes docs/openapi.json
  tests/           contract/, engine/, product/
```

### 5.1 The one rule: the contract

`backend/contract/schemas.py` defines every request and response shape. Conventions that never change:

- Timestamps are Unix epoch **seconds**, UTC.
- Amounts are token units as floats (`7850.0` means 7,850 USDT), never raw integers with decimals.
- Node types: `victim`, `scam_wallet`, `intermediary`, `bridge`, `mixer`, `exchange`, `unknown`.
- Hop numbers: `-1` for victims, `0` for the reported wallet, increasing downstream.
- Heuristic attribution confidence must stay **below 0.90**; only a direct label match goes higher.
- Every `nearest_vasp` carries evidence, and its deposit address must exist in the graph.

The engine returns the technical findings; the product side adds urgency, recommendations and monitoring on top. Changing the contract has a defined process in [CONTRACT.md](CONTRACT.md).

### 5.2 Engine: how a trace runs

1. **Adapter** (`engine/chains/tron.py`). Fetches USDT-TRC20 transfers for a wallet, converts timestamps to seconds and amounts to token units, and caches the raw response. It also detects the chain from an address format (TRON, Ethereum, Bitcoin, Solana).
2. **Tracer** (`engine/trace/tracing.py`). Walks forward, biggest and most recent transfer first. Each outgoing transfer becomes an edge. It stops at labeled endpoints, depth 5 and flows under 1% of the case value. It also marks pass-through wallets and computes idle balances.
3. **Attribution** (`engine/trace/attribution.py`). Looks for the nearest labeled exchange; chooses between the sweep heuristic and a direct match; builds the evidence list and fills in the nodal contact from `vasp_contacts.csv`.
4. **Seam** (`engine/__init__.py`). Runs 1 to 3 and returns one `TraceResponse`. It also exposes `new_transfers(addresses, since_ts)`, a light call the watcher uses to check a few wallets without a full re-trace.

### 5.3 Product: what happens after the trace

- `store.py` saves each case (summary plus full trace) in SQLite and stamps it with an urgency, an "as of" time and its monitoring status.
- `recommendations.py` turns the trace into an action list and the urgency rank.
- `alerts.py` runs the watcher in the background and serves alerts over server-sent events.
- `notices.py` fills the freeze-notice template from the trace.

### 5.4 API endpoints

All routes live in `main.py`; interactive docs are at <http://localhost:8000/docs>.

| Method | Path | Does |
|---|---|---|
| POST | `/api/trace` | Submit a complaint; run the engine; store and return the case |
| GET | `/api/cases` | All cases, newest first |
| GET | `/api/cases/{id}` | One case, full trace |
| GET | `/api/cases/{id}/freeze-notice` | Draft the freeze notice (404 when no exchange was found) |
| GET | `/api/cases/{id}/report` | The PDF evidence report for the case |
| POST | `/api/cases/{id}/simulate-movement` | Demo: replay a recorded movement of the idle funds |
| GET | `/api/wallets/{address}/risk` | Risk of one TRON wallet, scored from its own transfers (labeled exchange, bridge and mixer addresses get fixed values; an unknown or non-TRON address is Low with a reason saying it was not scored). Traced wallets are also scored inside `/api/trace` |
| GET | `/api/alerts`, `/api/alerts/stream` | Alert history and the live stream |
| GET | `/api/dashboard`, `/api/networks` | Figures and linked-complaint groups computed from the stored cases |
| POST | `/api/alerts/simulate` | Push the next scripted alert for a case (SIMULATED) |
| POST | `/api/integrations/ncrp/complaints`, `/api/integrations/sahyog/notice` | Mock NCRP and SAHYOG connectors: NCRP creates a case; SAHYOG marks the notice sent |
| GET | `/api/health` | Status, contract version and engine mode |

### 5.5 The data folder

```
data/
  reference/   labels.csv (exchanges, mixers, bridges), vasp_contacts.csv, LABELS.md
  cache/       raw TronGrid responses; SOURCES.md says which are real and which are scripted
  scenarios/   8 attribution scenarios (scenarios.json) + the live-monitoring replay feed
  seed/        the 8 seeded demo cases and their pre-built traces
  fixtures/    one example response per endpoint
  scripts/     the scripts that build all of the above
```

---

## 6. The frontend

React with Vite, Tailwind CSS for styling and Cytoscape for the graph.

```
frontend/src/
  pages/        Dashboard, NewComplaint, CaseView, NetworkView
  components/
    common/     Layout (sidebar, health check), Badges, PageHeader, Status, CopyButton, AlertFeed, Toasts
    case/       TraceGraph (with the hop-by-hop animation), NodePanel, NearestVaspCard, SummaryStrip,
                RecommendationsPanel, FreezeNoticeModal, Legend
    dashboard/  BarBreakdown (the breakdown charts)
    network/    NetworkGraph (one linked group of complaints)
  hooks/        useFetch (loading, error and reload for one API call), useAlerts (the live alert stream)
  lib/          api.js (the only place that talks HTTP), colors.js, format.js
```

Design rules that explain how it behaves:

- `lib/api.js` is the only file that calls the backend. In development Vite proxies `/api` to port 8000.
- Colors for node types, risk levels, urgency and data source are defined once in `lib/colors.js`.
- Every screen has a loading, error and empty state, so nothing is ever blank.
- The case page re-reads the case every 30 seconds and instantly when an alert for that case arrives.

Not built yet: the Demo Mode toggle (disabled in the sidebar). The trace graph animates hop by hop when a case opens (a button replays it), and alerts arrive as toasts and in a feed in the top bar.

---

## 7. The risk model: features, selection, training

> **Status: Step 6 is done.** Every traced downstream wallet carries a risk level, score and reasons, the case carries a fraud type, and `GET /api/wallets/{address}/risk` scores any TRON address on its own (`engine/model/risk.py`). On its own, a wallet's age is measured to its last transfer (there is no trace to say when funds arrived). The model is trained on synthetic data and its reasons are our assumptions; see the limits below.

### 7.1 What it answers

For each wallet downstream of the reported one: *how much does this wallet look like part of a fraud flow?* That ranks which hops an investigator should follow first. The reported wallet itself is not scored: a victim already named it.

Wallets that are labeled get fixed values instead of a model score: exchange Low, bridge Medium, mixer Critical. The model scores the unlabeled wallets, the intermediaries and unknowns.

### 7.2 The seven features

All computed from a wallet's USDT transfers in `backend/engine/model/features.py`:

| Feature | Meaning | Scam-like looks like | Why it is a signal |
|---|---|---|---|
| `age_days` | Days from the wallet's first transfer to when the traced funds arrived | Very young | Mule wallets are often created just before use |
| `tx_count` | Transfers touching the wallet | Very few | A wallet with a short history has little legitimate use |
| `in_out_ratio` | Amount sent divided by amount received (capped at 1) | Close to 1 | Pass-through wallets keep nothing |
| `median_forward_sec` | Typical time from money arriving to being sent on (weighted by deposit size, so dust cannot hide a big fast forward) | Minutes | Fast forwarding is the signature of laundering |
| `unique_senders` | Distinct wallets that paid it | Many (for a collector) | Collectors receive from many victims |
| `round_number_ratio` | Share of transfers with round amounts (multiples of 50 USDT) | High | Scam payments are often fixed round sums |
| `fan_in_degree` | Unique senders divided by unique recipients | High | Many in, few out means consolidation |

Age is measured **at the moment funds arrived**, not from today. This keeps the numbers identical on cached data and avoids a wallet looking more innocent each day. For a standalone "score this address" request, the wallet's last transfer is used instead.

### 7.3 How the features were selected

They come from the build plan (DEMO.md Step 6) and were chosen on three rules:

- **Computable from transfers alone.** No outside data or identities are needed, so the model works on any wallet we can fetch.
- **Explainable in a sentence.** Each one maps to plain-language wording ("forwards funds in 4 minutes", "89 unique senders") so an officer can read why a wallet scored high.
- **Aimed at the behaviours in the problem:** layering and pass-through (forward time, in/out ratio), collection (unique senders, fan-in), and disposable wallets (age, transaction count, round amounts).

There is no automatic feature selection and no learned feature search: with seven hand-picked, interpretable inputs that was unnecessary.

### 7.4 Scoring and training

- **Rules** (`engine/model/rules.py`): a hand-written 0 to 1 formula, used as a baseline and as the fallback if the trained model is missing. Two profiles, mule and collector, each gated so one trait cannot score high alone. Levels: below 0.25 Low, below 0.50 Medium, below 0.75 High, else Critical (placeholders).
- **Training data** (`engine/model/synthetic.py`): about 6,000 synthetic wallets from 11 profiles (fast and slow mules, collectors, splitters on the fraud side; normal and new users, exchange hubs, bots, OTC desks, savers, charities and merchants on the other), 40% fraud-labeled, with wide overlapping ranges and 3% flipped labels. The first version made round amounts and wallet age near-perfect separators, so the model leaned on them (40% and 32% of its importance) and ignored forwarding speed. The ranges were widened until no single feature separates the classes (the best alone reaches an AUC of 0.83) and the model no longer relies on any one feature.
- **Model** (`engine/model/train.py`): XGBoost, fixed random seed, with direction constraints (younger, faster-forwarding and more-forwarding wallets are never less risky). 13 seed rows from our scripted cases are added to training; 25% of the synthetic data is held out. Saved to `data/models/risk_model.pkl` by `python data/scripts/train_risk_model.py`.
- **Reasons** (`engine/model/scoring.py`): the three features that pushed a wallet's score up most (SHAP), as sentences with the real values. A Low wallet says "No strong fraud signals". A wallet with a single transfer, or a few that only came in, is capped at Medium with "Too little transaction history to judge".
- **TronGrid failures and big traces:** a live fetch that fails (rate limit, timeout, server error) leaves that wallet as an unread leaf and the trace carries on; the case notes say how many wallets could not be fetched and why. A trace reads at most 40 wallets and for at most 30 seconds (both placeholders), biggest flows first, and says so when it stops early. A failed live check by the watcher is never treated as "nothing moved": the case goes stale.
- **Unusual wallets:** the tracer ignores transfers a wallet makes to itself, follows only what left the reported wallet after the victim paid it (using the complaint's payment transaction when it is given), counts the same transfer listed twice once, treats a missing, zero or negative amount as unknown, and flags the reported wallet's own balance as idle funds when it still holds the money. If the reported wallet is itself a known exchange, mixer or bridge, the case notes say so (an exchange address is attributed at hop 0). Two exchanges at the same distance are separated by the bigger flow.
- **Crossing a bridge (seeded, simulated):** when a traced transfer goes into a known bridge and the repo has a seeded exit for that exact transfer (`data/cache/bridge_legs.json`), the trace continues onto the other chain using seeded transfers (`data/cache/evm/`, read by `engine/chains/evm_stub.py`). Only the hero case has one, so the live hero trace now finds the 3,720 USDT sitting on the Ethereum side and the case is Act now. Nothing here comes from a real chain. The model scores TRON wallets only, so a wallet that received bridged funds gets a fixed High 0.74 with the reasons "Received bridged funds" and "No outflow yet".
- **Partly fetched histories:** TronGrid returns at most 200 transfers per page, so a busy wallet's age and transfer count can be wrong (a years-old exchange wallet looked 18 days old). The adapter now records whether a history was truncated (`TronAdapter.history_truncated`), and a truncated wallet is capped at Medium, with a reason saying so and never quoting its age or transfer count.
- **Scenario batteries** (`engine/model/battery.py`): simulated transfer histories for 19 DEV and 13 HOLDOUT scenarios (mules, collectors, splitters, normal users, bots, OTC desks, salary accounts, charities and more), run through the real feature extraction and scorer. The DEV set guided the fixes; the HOLDOUT set uses different ranges and new scenario types and was run once. Run them with `python data/scripts/eval_risk_battery.py [--holdout]`.
- **Typology** (`engine/model/typology.py`): a rule-assisted classifier for the fraud type, from how a reported wallet's money came in and left. Signatures, checked in order: ransomware (a few large payments and much of the money to a mixer), sextortion (many different payers each paying a small amount once), task scam (many payers repeating small payments, consolidated within a day), phishing (a brand-new wallet receiving a few non-round payments and forwarding within the hour), investment scam (several payers, mid to large amounts, consolidated fast). A wallet over 120 days old, or with no match, is `unknown`; `darknet` has no signature and is never returned. It is checked on its own scenario batteries (`python data/scripts/eval_typology_battery.py [--holdout]`): 99% on the DEV set and 94% on the holdout, where the cut-offs for "a few", "large" and "fast" bite at the edges. The signatures and thresholds are our assumptions.

Results (our own scenarios and labels): the scorer passes 98% of the DEV scenarios and 99% of the HOLDOUT ones; the first model passed 60% and 48%. On the held-out synthetic data the model reaches an AUC of 0.96 against 0.87 for the rules.

### 7.5 Limits to know

- **The model learns our assumptions.** Synthetic data comes from ranges we chose, so the model's score reflects those assumptions, not measured fraud behaviour. The held-out synthetic score will look good for that reason and proves little.
- **Real wallets differ.** The three real Tether-flagged wallets in the cache score Low (0.04 to 0.21): they are old and forward slowly, which is not the pattern we simulated. We did not tune to them. Real labeled data, such as confirmed complaint wallets, would be needed for a trustworthy model.
- **The test scenarios are ours too.** The batteries show the scorer is robust across many variations of what we believe fraud looks like, not that those beliefs are right.
- **"Flagged" is not "convicted".** The real wallets are Tether-frozen addresses. Tether does not publish why.
- The interface and the slides must say the model is trained on synthetic and seed data.

---

## 8. How to read the website

### 8.1 The pages

| Page | What it shows |
|---|---|
| **Dashboard** | KPI tiles (cases, amount lost, amount traced, share with an exchange identified, average time to attribution, idle funds flagged), breakdown charts by fraud type, receiving exchange and state, and a table of recent cases: case, complaint, wallet, amount lost, fraud type, state, **urgency**, exchange, time to attribution, status. Click a case to open it. |
| **New Complaint** | The form that starts a trace. "Fill hero example" loads the demo case. The chain is detected from the address. |
| **Case View** | One case in full. See below. |
| **Networks** | Groups of complaints that share a scammer wallet. Each group shows its victims, total lost, states, receiving exchange and what links them, with a graph of how the complaints connect. |

### 8.2 Urgency: the badge that matters most

Shown at the top of every case and as a column on the dashboard. First rule that matches wins; hover or read the "Why …" line to see the exact triggers.

| Badge | Fires when | What it means |
|---|---|---|
| **Act now** (red) | There are idle funds at the last check; or funds sit at an exchange deposit address that has not been swept yet; or a fresh transfer (under 15 minutes old) left a case wallet | A freeze may still be possible. Contact the exchange first. |
| **Act soon** (amber) | An exchange was identified at 0.70 confidence or higher; or the amount lost is 10,000 or more; or the case is linked to 2 or more other complaints | The money has probably moved on; build the case and send the request promptly. |
| **Preserve** (blue) | Everything else, for example the money entered a mixer or no exchange was found | Keep the evidence and keep monitoring. |

The thresholds (15 minutes, 0.70, 10,000, 2 complaints) are placeholders for investigators to tune. Urgency can go **down** as well as up: if idle funds move to an exchange, Act now becomes Act soon, and the reasons say why.

### 8.3 Under the badge: "as of" and Live / Stale

- **as of 14:32:10** is the time of the last successful check of the chain, not the time something last changed. A quiet case still shows a fresh time.
- **Live** (green dot) means the watcher checked recently.
- **Stale** (amber) means the last check is older than twice the poll interval. The page shows a warning that the urgency may be out of date.
- **Monitoring off** means the watcher is switched off.

### 8.4 The fund-flow graph

- **Node colors:** victim grey, scam (reported) wallet red, intermediary orange, bridge blue, mixer purple, exchange green, unknown white.
- **Edge thickness** shows the amount. A green path is the route to the Nearest VASP. Dashed edges are bridges or mixers. An **amber ring** marks a wallet still holding funds.
- **Click a wallet** to open its panel on the right: type, chain, hop, typology, risk badge with reasons, any idle balance, and its incoming and outgoing transfers. The reported wallet shows a **Reported** badge instead of a risk, since it is not scored.

### 8.5 The Nearest VASP card

The answer to "which exchange got the money":

- **Exchange** and the **deposit address** at it, with how many hops away it is, the amount and the time.
- **Confidence** and the **method** tag:
  - `deterministic`: the trace reached an address in our label list. Confidence is a fixed 0.95.
  - `heuristic`: the sweep pattern. Confidence is a weighted score, always below 0.90.
  - Neither is a probability. 0.95 means "the destination matches a known label", not "95% chance a freeze works".
- **Evidence:** the facts behind the call, for example "14 different wallets over 66 hours" and "99% forwarded to the labeled hot wallet".
- **Contact:** the exchange's nodal officer from the contact list (mock contacts in the demo).
- When no exchange is reached the card shows an empty state and the notice button is disabled.

### 8.6 Other items on a case

- **Summary strip:** amount lost, total traced, **idle funds** (highlighted when above zero), hops and node count, time to attribution, urgency, and the **data source** badge.
- **Data source badge:** `LIVE` (fetched from TronGrid), `CACHED` (read from saved responses), `SIMULATED` (fictional demo data).
- **Recommendations panel:** ordered actions such as "Act on idle funds", "Issue freeze and KYC request to X", "Continue trace on Ethereum" (after a bridge) or "Preserve mixer evidence".
- **Freeze Notice button:** opens a draft addressed to the exchange, citing the transaction path, and asking for a freeze plus preservation of KYC, bank, phone and IP data. Legal references are placeholders.
- **Download Report:** a PDF evidence report: summary, the fund-flow graph, transaction table, attribution evidence, wallet risk, recommendations, and methodology and limits. Every page footer carries a SHA-256 hash of the case data it was built from.
- **Alerts:** when the watcher raises an alert for this case it appears under the summary and the page refreshes; all alerts also appear as toasts and in the alert feed in the top bar. The Simulate button replays a recorded movement when the engine is on, and otherwise steps through a scripted sequence built from the case (always labeled simulated).

### 8.7 A two-minute tour (with live monitoring)

1. Open **New Complaint**, enter wallet `TJgNArE5dkoiDgHUjimdizwNaTZZwLh1Lg`, amount `6000`, submit.
2. The case says **Act now** because 5,900 USDT is idle in the last wallet (amber ring on the graph). No exchange is named yet.
3. Click **Simulate fund movement**. A recorded transfer (labeled SIMULATED) moves the money to Example Exchange B.
4. Three alerts appear (funds moved, reached an exchange, urgency changed). The graph extends, the Nearest VASP card names Example Exchange B at 0.95 (`deterministic`) and the badge drops to **Act soon**.
5. Open **Freeze Notice** to see the draft request.

A real flow: wallet `TVLHfdgpiMR2mRpjtAWm8YJ5hCj9iYWS2B` (amount `2826`) is a real TRON wallet whose money went through a real deposit address into a wallet labeled Binance; the engine attributes it to Binance by the sweep rule. It is not claimed to be fraud, and the Binance label is unverified (see `data/cache/SOURCES.md`).

Other wallets worth trying (all fictional): `TXCFXFx5tuZ1ky3HgTEHZpoLxXmJ32XLvj` (direct match, 8000), `TDongf8XirZvCUFazHwM2FG7cukpnF9h9D` (sweep heuristic, 5000), `TPA2pH1ZJWxMFeyMDEup4JQg51kkcVUMKe` (ends at a mixer, 4000), `TMmiNnkHcoyUuNbK7TPwwTfr8ofi82Kohz` (ends at a bridge, 4000). All 8 scenarios are listed in `data/scenarios/scenarios.json`.

The seeded cases on the dashboard (C-001 to C-008) show the other situations: shared deposit addresses across complaints, a case ending in a mixer, an isolated case, and a case that left TRON through a bridge with idle funds.

---

## 9. Data and its honesty limits

- **Fictional:** the hero case, the example exchanges, bridges and mixer, the 8 scenarios, the seeded cases and their wallet addresses.
- **Real:** three TRON wallets that Tether froze on 2026-10-20, with their USDT-TRC20 history from TronGrid, plus a few real exchange wallets in `labels.csv` whose labels come from a Dune query and are **not independently verified**. See `data/cache/SOURCES.md` and `data/reference/LABELS.md`.
- **The label list is small.** A real deployment needs a much larger, verified one.
- **No real bridge or mixer label on TRON** is in the list yet.
- **NCRP and SAHYOG links are simulated.**
- **"Live" means polling.** There is always a delay of up to one poll interval plus block confirmation time. Only leaf and idle wallets are watched, because public APIs have rate limits. The demo's fund movement is a recorded replay, labeled SIMULATED.
- **Live monitoring improves how current the reading is.** It cannot make `Act now` mean a freeze will succeed.
- **The risk model** (when built) is trained on synthetic and seed data; see [section 7.5](#75-limits-to-know).

---

## 10. Tests

Run from the repo root (or from `backend/`); all tests run offline:

```bash
pytest -q
```

| Folder | Covers |
|---|---|
| `backend/tests/contract/` | Engine output matches the contract (graph shape, exchange in graph, idle funds add up) |
| `backend/tests/engine/` | TRON adapter, tracing rules, attribution, the 8 attribution scenarios end to end, the model features, rules, training, scoring, the scenario batteries, resilience and edge cases, and a contract-and-speed check of every cached wallet |
| `backend/tests/product/` | Seed cases and traces, the case store and API, urgency rules, live monitoring, alerts and replay, the PDF report, dashboard and network analytics, the mock NCRP and SAHYOG endpoints |

Frontend: `cd frontend && npm test` runs the page and routing tests, and `npm run build` checks it compiles.

---

## 11. Project status and further reading

| Step | State |
|---|---|
| 1 to 3: contract, routes, cache, labels, hero case, TRON adapter | Done |
| 4: tracing engine | Done |
| 5: attribution | Done |
| Live monitoring, urgency, contract v1.1.0 | Done |
| 6: risk model and typology | Done (trained on synthetic data; see section 7 for the limits) |
| 7: PDF report, freeze notice, recommendations | Done |
| 8: alerts, mock NCRP and SAHYOG, API spec (`docs/openapi.json`) | Done |
| 9: dashboard, Network View, trace animation | Done |
| A7 hardening, a real second case, the cross-chain continuation | Done |
| Demo Mode toggle, a clean-start run of the 5-minute script, slides | Not done |

Documents in this repo:

- [DEMO.md](DEMO.md): the full build plan, the demo script, the team split and the detailed progress log.
- [CONTRACT.md](CONTRACT.md): the API contract in plain language and the process for changing it.
- `data/cache/SOURCES.md`, `data/reference/LABELS.md`: where the data came from.
