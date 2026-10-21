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
12. [Guide: using the website](#12-guide-using-the-website)

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

First thing to try: **File a complaint**, click **Fill demo example** and submit; you get a complaint ID. Then open the **officer console** in the other tab: the complaint is in the **Inbox** (a count shows on the Inbox link, and an alert pops up). Open it, click **Start review** and **Trigger trace**: the case is created and you land on it. Five complaints are already waiting in the inbox: four demo cases, one for each way the money can end, and the real Binance flow. **Exchange (VASP)** is `NCRP-2026-104317` (a sweep to an exchange deposit address), **DEX** is `NCRP-2026-470218` (swapped on a pool with no account holder), **mule bank account** is `NCRP-2026-258846` (the victim paid a bank account and funds still sit in a wallet), and **stalled** is `NCRP-2026-582904` (the money enters a mixer). Each one's description in the inbox says which it is. Filing never traces: only an officer does. The form also asks, optionally, how the scammer reached the victim and where they paid (phone, chat handle, website, app, UPI ID, bank account). Those, with the wallets found by the trace, go into the case's **identifier ledger**, and the case page shows **Leads**: which institution holds the identity behind each identifier (exchange, bank, UPI app, telecom operator, messaging platform, domain host, app store, token issuer) and what to ask. They are suggestions for an officer; nothing is sent. The case page also shows **Requests to institutions**: from any lead an officer can draft a letter (a preservation notice, KYC, account details, freeze, subscriber details, platform data, registrant or developer details, takedown, token hold). Each letter is a draft with placeholder legal references, names and dates, and never contains the victim's personal details. An officer reviews it, **approves** it (nothing can be sent unapproved) and sends it. Nothing is transmitted in this demo: the acknowledgement and the reply come from a demo button, and every reply is fictional (marked FICTIONAL DEMO DATA). A reply adds the identifiers it mentions to the case (a registered phone, email, device, IP, a mule bank account), which opens new leads, so an investigation can go round after round. Some complaints share the same fictional person on purpose, so their replies contain the same phone, email or device. The case page also shows **Where the money went**: each kind of endpoint is handled differently. An **exchange** can be asked for KYC and told to freeze. A **DEX** swap pool has no account holder at all (the trace stops there; follow the swapped tokens and ask the token issuer to hold any USDT left). A **bank account** the victim paid needs a freeze or lien request to that bank. A **mixer** cannot be followed. A **bridge** means continue on the other chain. And **funds still in a wallet** can be held by the token issuer now. **Suspected mules** (wallets that passed the money on, and the accounts the victim paid) are listed with what they received, passed on and where it went. They are only suspected: the holder of a mule account is often a victim too. **Linked cases and suspected people** shows which complaints share an identifier (one strong match, or two weaker ones, link cases into one possible operation) and who the institutions' replies name, each with a confidence that is capped and labelled an inference. A **referral dossier** (PDF) gathers the money trail, mules, identifiers, requests and replies, linked cases and a checklist of records, inferences and gaps for the investigating agency, without the victim's personal details; recording a referral stores the dossier's SHA-256. Any arrest or legal action is for the agency. **Report and cease** is the last step: the evidence report, then one click drafts every freeze, hold and takedown request the case allows (the exchange, the bank, the token issuer for funds still in a wallet, the platforms and domains behind the lure). The officer approves and sends each one; a takedown is flagged until the preservation notice has gone first. The first freeze, hold or takedown sent (or the exchange notice) moves the complaint to **Action initiated**, and closing the complaint is a separate officer step that never closes an open request. A **Demo** button runs the whole investigation in one click, simulated. The citizen can then follow it on **Track a complaint** with the complaint ID: a progress bar, one plain sentence for the current stage (including Action initiated and Closed) and the times each stage began, and nothing else (the page reads only those fields, the server never sends more, and the lookup is rate limited and never cached).

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
| POST | `/api/complaints` | A citizen files a complaint: returns a random complaint ID; nothing is traced |
| GET | `/api/complaints/{id}/status` | What the citizen may see: the stage and a generic message (rate limited) |
| GET | `/api/officer/complaints` | The officer inbox (`?stage=received` for new ones) |
| GET | `/api/officer/complaints/{id}` | One complaint in full |
| POST | `/api/officer/complaints/{id}/review`, `/trace` | Start the review; trigger the trace (creates the case) |
| GET, POST | `/api/officer/cases/{id}/identifiers` | The investigation ledger: wallets, bank accounts, UPI IDs, phones, handles, domains and apps involved in a case; an officer can add one |
| GET | `/api/officer/cases/{id}/leads` | Suggested next steps: for each identifier, which institution holds the identity behind it and which requests to send (nothing is sent automatically) |
| GET | `/api/officer/cases/{id}/outcomes`, `/mules` | Where the money went, with the handling each kind of endpoint needs (exchange, DEX, bank account, mixer, bridge, funds still in a wallet), and the suspected mule wallets and accounts |
| GET, POST | `/api/officer/cases/{id}/requests` | Requests to institutions: draft a letter from a lead; an officer reviews, approves and sends it (nothing is transmitted in the demo) |
| POST | `/api/officer/requests/{id}/approve`, `/send`, `/simulate`, `/close` | Move a request along; `simulate` is a demo button that gives an acknowledgement and then a fictional reply |
| POST | `/api/integrations/ncrp/complaints`, `/api/integrations/sahyog/notice` | Mock connectors: NCRP puts a complaint in the officer inbox; SAHYOG marks the notice sent |
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

---

## 12. Guide: using the website

A walk through every page, what each thing on it stands for, and the scenarios to try. It explains what you are looking at, not how it is built.

> **All the data you will see is synthetic.** The people, wallets, exchanges, banks, phone numbers, websites, replies and letters are invented for the demo (exchanges are called "Example Exchange A/B/C", demo people carry "(demo)", phone numbers are 90000 00xxx, domains end in `.example`), with two exceptions noted in section 9. Nothing is ever sent to anyone: every "send" is recorded only, and every acknowledgement and reply is simulated.

### 12.1 The three areas

| Area | Who it is for | What it is |
|---|---|---|
| **Gateway** (`/`) | Anyone | The page a citizen reaches from an official government website. It only hands people on. |
| **Citizen side** (`/citizen/...`) | A victim | File a complaint, then follow it with the complaint ID. |
| **Officer console** (`/officer/...`) | An investigator | Review complaints, trigger the trace, work the case, act, and close. It opens in its own browser tab and has no login in the demo. |

A citizen can never see the officer side, and the tracker never shows how a complaint is being handled.

### 12.2 The gateway

- **The message in the middle** says you have been handed over from an official website. It stands in for the link from a government portal.
- **The moving graph behind it** is decoration: dots are wallets, lines are payments, the pulses are money moving. It stands for what the product does.
- **The side panel** lists the portal's services: *Track a complaint*, *File a complaint*, and the *Officer console* (which opens a new tab). It can be collapsed to a thin rail and remembers your choice.

### 12.3 The citizen side

**File a complaint.** The form asks for three kinds of thing:

| Section | What it stands for |
|---|---|
| **About you** (name, 10-digit mobile) | Who reported. Officers see it; it never goes into a letter to an institution or into the referral dossier. |
| **The money** (wallet, network, amount, transaction ID, fraud type, state, description) | What was lost and where it was sent. The network is detected from the address. Only TRON wallets are traced; other networks are accepted and noted. |
| **How they reached you, and where you paid** (optional: scammer's phone, chat handle and app, website, app name, UPI ID, bank account and IFSC) | Each one is a thread to a real person. A phone number leads to a telecom operator, a website to a registrar, a UPI ID or bank account to a bank. They are optional, but the more you give, the more the officer can follow. |

"Fill demo example" fills the form with a made-up complaint. Filing **does not start a trace**; only an officer does that.

**Submitted.** You get a complaint ID such as `NCRP-2026-123456`. It is random, so it cannot be guessed. Keep it: it is the only way to follow the complaint.

**Track a complaint.** Enter the ID. You see a progress bar, one plain sentence for where it stands, and the time each stage began. Nothing else, ever: not the wallet, the amount, the exchange, or what officers are doing.

| Stage | The sentence a citizen sees |
|---|---|
| Received | Your complaint has been registered. |
| Under review | An officer is reviewing your complaint. |
| Investigation in progress | Your complaint is being investigated. |
| Action initiated | Action has been initiated with the relevant institutions. |
| Closed | Your complaint has been closed. For details, please call the National Cyber Crime Helpline 1930. |

An unknown ID gets one generic "not found" message. To try the tracker without filing, use a seeded ID: `NCRP-2026-0001` (investigating) or `NCRP-2026-0003` (action initiated).

### 12.4 Wallets to copy and paste

Paste these into **File a complaint** if you would rather not use "Fill demo example". Each one is in the demo cache, so it traces without any key. The amount is what to enter as the amount lost.

| Wallet | Amount | What you will see |
|---|---|---|
| `TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo` | 12000 | The main demo case: money reaches **Example Exchange A**, some still sits idle, some crosses a bridge to Ethereum, and some enters a mixer. |
| `TDongf8XirZvCUFazHwM2FG7cukpnF9h9D` | 5000 | **Exchange (VASP):** many senders feed one deposit address that sweeps to **Example Exchange B**. Named by a pattern, so confidence is below 90%. |
| `TXCFXFx5tuZ1ky3HgTEHZpoLxXmJ32XLvj` | 8000 | **Direct match:** the money lands straight on a known **Example Exchange C** wallet. Confidence 95%. |
| `TJYp7BbgZuBiEytM4gAn8jv42BFESS9PEf` | 4000 | **DEX:** the money is swapped on a decentralised pool. There is no account holder to ask. |
| `TJgNArE5dkoiDgHUjimdizwNaTZZwLh1Lg` | 6000 | **Funds still idle:** 5,900 sit in the last wallet, so it is urgent. Add the bank details below to see the **mule bank account** case. |
| `TPA2pH1ZJWxMFeyMDEup4JQg51kkcVUMKe` | 4000 | **Stalled:** the money enters a mixer and cannot be followed. |
| `TMmiNnkHcoyUuNbK7TPwwTfr8ofi82Kohz` | 4000 | **Bridge:** the money crosses to another chain. |
| `TVLHfdgpiMR2mRpjtAWm8YJ5hCj9iYWS2B` | 2826 | A **real** TRON flow that ends in a wallet labelled Binance. Not claimed to be fraud; the label is unverified. |

Optional "how they reached you" values to type in, for the scenarios below (all fictional):

| For this scenario | Type in |
|---|---|
| Mule bank account | On the idle wallet `TJgNArE5dk…`: bank account `000123450001`, IFSC `HDFC0000001` |
| Linked operation | On the main wallet `TUNoHG2D7i…`: website `hero-invest.example`, UPI ID `hero.invest@okaxis` |
| A phone and a chat handle | Phone `+91 90000 00101`, handle `@alpha_returns_demo` on Telegram |

Five complaints are also **already waiting in the officer inbox**, so you can skip filing: the four demo cases (`NCRP-2026-104317` exchange, `NCRP-2026-470218` DEX, `NCRP-2026-258846` mule bank account, `NCRP-2026-582904` stalled) and the real flow `NCRP-2026-391502`.

### 12.5 The officer console

The left menu has **Inbox**, **Dashboard** and **Networks**. A number on Inbox counts complaints waiting for review, and a pop-up appears when a new one arrives.

**Inbox.** Every complaint, newest first, filtered by *New*, *In progress*, *Action taken* and *All*. Each row shows the complaint ID, when it came in, the reporter, the wallet, the amount, the fraud type, the state and the **stage**.

**A complaint.** The full complaint: the reporter, the wallet, the amount, and a panel on how the scammer reached the victim and where they paid. The side panel is the **history**: each stage change with its time and an officer-only note. The buttons mirror the stages:

- **Start review** moves it from Received to Under review.
- **Trigger trace** runs the trace and creates a **case**, then takes you to it. This is the moment the citizen's tracker changes to "being investigated".
- **Open case** appears once a case exists.

### 12.6 The case page, top to bottom

**Header.** The case ID, the complaint ID, the fraud type and the reported wallet.
- **Simulate fund movement** replays a recorded transfer so you can see live monitoring react. It is labelled simulated.
- **Freeze Notice** opens a draft request to the exchange. Legal references are placeholders.
- **Download Report** gives the PDF evidence report.

**Summary strip.** *Amount lost*; *total traced* (how much of it the trace followed); *idle funds* (still sitting in wallets, highlighted when above zero, because that can still be frozen); *hops* and *wallets* in the trace; *time to attribution*; the **urgency badge** (section 8.2); and a **data source** badge: `LIVE`, `CACHED` or `SIMULATED`. The "as of" time and the **Live / Stale** dot say how recently the chain was checked.

**The fund-flow graph.** The money, left to right, from the victim.
- **Colours:** victim grey, reported wallet red, intermediary orange, bridge blue, mixer purple, exchange green, DEX teal, bank account yellow, unknown white.
- **Thick lines** carry more money. A **green path** is the route to the exchange that got the money. **Dashed lines** are bridges and mixers; a **swap** edge is a DEX. An **amber ring** marks a wallet still holding funds.
- A node can be an **intermediary**: a wallet that forwards most of what it receives within an hour, which is the signature of a mule wallet.
- **Click a wallet** for its panel: type, network, hop, typology, a risk badge with its reasons, any idle balance, and its transfers in and out. The reported wallet shows "Reported" instead of a risk, because it is not scored.

**Nearest exchange card.** Which exchange got the money, the deposit address there, how many hops away, the amount and the time, the **confidence**, and the **evidence** behind it. Two methods: `deterministic` (the trace landed on a known exchange wallet, 95%) and `heuristic` (a sweep pattern, always under 90%). Confidence means "how sure the label is", not "the chance a freeze works". It also shows the exchange's contact (a mock contact here).

**Recommendations.** The next actions in order, such as "Act on idle funds", "Issue freeze and KYC request to the exchange", "Follow the swap" for a DEX, "Continue the trace on Ethereum" after a bridge, or "Preserve mixer evidence".

**Where the money went.** One card per endpoint the money reached, each handled differently:

| Endpoint | What it means | What the officer does |
|---|---|---|
| **Exchange (VASP)** | The money reached an account at an exchange that holds the customer's identity | Ask for KYC and a freeze; the reply may list bank accounts and phones |
| **DEX swap** | Swapped on a pool: no account holder, nothing to freeze | Follow the swapped tokens, ask the token issuer to hold any USDT left, keep the swap as evidence |
| **Bank account** | The victim paid a bank account (or a reply named one) | Freeze or lien request to that bank, plus account details |
| **Mixer** | Cannot be followed through | Preserve the evidence, watch the exits |
| **Bridge** | The money crossed to another chain | Continue the trace there |
| **Funds still in a wallet** | Money not yet moved | Ask the token issuer to hold it now |
| **Dead end** | The trace ended with none of the above | Check the leads, keep watching |

**Suspected mules.** Wallets that passed money on, and bank accounts the victim paid, with what each received and forwarded and where it went. *Suspected* is deliberate: the holder of a mule account is often a victim too.

**Leads and identifiers.** The *identifier ledger* is every fact the case knows about the people behind the fraud: wallets, bank accounts, UPI IDs, phones, handles, domains, apps. Each becomes a **lead**: the institution that holds the identity behind it (exchange, bank, payment app, telecom operator, messaging platform, domain host, app store, token issuer), what it can tell you, and a priority (urgent, high, normal).

**Requests to institutions.** A request is a drafted letter for a lead. Its status moves **Draft, Approved, Sent, Acknowledged, Replied, Closed**, and a letter cannot be sent before it is approved. Letters are drafts with placeholder legal text, and never contain the victim's personal details. In the demo the acknowledgement and reply come from buttons, and every reply is marked FICTIONAL DEMO DATA. A reply adds new identifiers (a registered phone, an email, a device, an IP, a mule bank account), which open new leads, so one answer leads to the next question. **Demo: simulate the whole investigation** does all of this in one click.

**Linked cases and suspected people.** Complaints are **linked** when they share one strong identifier or two weaker ones, which suggests one operation. The panel shows the linked cases, total lost and states, and each shared identifier with its strength. **Suspected people** are named only by institutions' replies, each with a confidence that is capped and always an inference, plus the evidence behind it. A mule account holder is shown at low confidence with a note that they may be a victim.

**Referral dossier.** A PDF for the investigating agency: the money trail, mules, identifiers, requests and replies, linked cases, and a checklist of what is a record, what is an inference and what is missing. It leaves out the victim's personal details. **Record referral** logs which agency it went to with the dossier's SHA-256. Any arrest or legal action is for the agency.

**Report and cease.** The last step. It offers the evidence report, then drafts every freeze, hold and takedown request the case allows. A takedown is flagged until the preservation notice has gone first. The first one sent moves the complaint to **Action initiated**; the panel shows the exact sentence the citizen now sees. **Close the complaint** ends the case without closing any open request.

### 12.7 The dashboard and networks

**Dashboard.** Six tiles: *Cases* (with how many are open and closed), *amount lost*, *amount traced*, *exchange identified* (the share of cases where an exchange was named), *average time to attribution* and *idle funds flagged*. Below are breakdowns by fraud type, receiving exchange and state (switch between number of cases and USDT lost), the **Recent cases** table (each case's **Open or Closed**, urgency, exchange, network and status), and a **Live alerts** feed. A case is *open* until its complaint is closed.

**Networks.** Groups of complaints that share a scammer wallet. Each shows its victims, total lost, states, the receiving exchange and what links them, with a graph of how the complaints connect. A group like this is called an *organised network*.

### 12.8 Scenarios to walk through

1. **Exchange (VASP).** Trace `NCRP-2026-104317`. The graph ends at Example Exchange B; the card names it with a confidence below 90%. *Where the money went* says to send KYC and a freeze to the exchange. Run **Demo: simulate the whole investigation**, then open *Linked cases and suspected people*: a reply names an account holder, and it lists a bank account as a suspected mule.
2. **DEX.** Trace `NCRP-2026-470218`. The graph stops at a teal DEX node. The card says there is no account holder and no freeze possible; the only action on offer is a takedown of the scam website and chat account. This is the case to show that not every trail ends at a person.
3. **Mule bank account.** Trace `NCRP-2026-258846`. There are two outcomes: money still sitting in a wallet (urgent: a token hold) and a bank account the victim paid (a freeze to the bank). After the demo run, the bank's reply names a holder and sometimes a further account the money moved on to, until the trail runs out as a cash withdrawal.
4. **Stalled.** Trace `NCRP-2026-582904`. The money enters a mixer, so there is nothing to freeze. The urgency is "Preserve". The only action is to preserve evidence and watch. Close the complaint to see the citizen's closing sentence.
5. **Funds still idle, then they move.** Trace `TJgNArE5dkoiDgHUjimdizwNaTZZwLh1Lg`. It is "Act now" with an amber ring. Press **Simulate fund movement**: alerts fire, the graph extends to Example Exchange B, and the badge drops to "Act soon".
6. **A linked operation.** File the main wallet `TUNoHG2D7i…` with website `hero-invest.example` and UPI `hero.invest@okaxis`, then trace it. *Linked cases and suspected people* shows it linked to the three seeded hero-invest complaints through those shared identifiers. Run the demo investigation and the same person is named by several institutions across several cases, at a higher confidence. Open **Networks** to see the group.
7. **A bridge.** Trace `TMmiNnkHcoyUuNbK7TPwwTfr8ofi82Kohz`. The graph ends at a blue bridge node and the recommendation is to continue on the other chain.

### 12.9 What the operator does, from complaint to close

1. **Watch the inbox.** A new complaint appears with a pop-up and a count on the menu. The citizen's tracker says *Received*.
2. **Open it and start the review.** Read the wallet, the amount, and where they paid. The tracker says *Under review*.
3. **Trigger the trace.** A case is created and you land on it. The tracker says *Investigation in progress*.
4. **Read the case.** The urgency badge says how fast to move. The graph and the *nearest exchange* card say where the money went. *Where the money went* says what each endpoint needs.
5. **Work the leads.** Draft a letter for each lead, approve it, and send it. Preserve first where records could be deleted. Replies come back, add new identifiers, and open new leads; repeat.
6. **Link and name.** Check the linked cases and the suspected people, and treat them as inferences to confirm. Mule account holders may be victims.
7. **Report and cease.** Download the evidence report, draft the freeze, hold and takedown requests, and approve and send them. The tracker moves to *Action initiated*.
8. **Refer.** Download the dossier, record the referral to the agency, and leave any arrest to them.
9. **Close.** Close the complaint. The dashboard shows the case as Closed, and the citizen is pointed to the 1930 helpline.

### 12.10 How the trace works, and where it stops

**The trace is best-first search, not breadth-first.** Breadth-first search would read wallets level by level. This one keeps a priority queue and always reads next the wallet that received the **largest, then most recent**, transfer. Starting from the reported wallet it repeats:

1. Take the next wallet and read its outgoing USDT transfers from the blockchain. This is public data, so no credentials are involved.
2. Turn each transfer into an edge and each receiver into a node, and queue the receivers. A wallet already seen is never read twice, so loops end.
3. Stop expanding at a labelled **exchange, bridge, mixer or DEX pool**, at **depth 5**, and for flows under **1%** of the case value.
4. Read at most **40 wallets in 30 seconds**. Largest-first means that budget is spent on the money that matters most.
5. Tag a wallet that forwards 90% or more of what it received within an hour as an **intermediary**, the usual pattern of a mule wallet.
6. Check the leaf wallets for an **idle balance**.

The whole on-chain trace runs in one go. It does not pause, and it needs no manual input.

**Where it stops, and why.** A blockchain is public, but an exchange's customer records and a bank's accounts are not. At a labelled exchange deposit address the chain ends: the trace can name the exchange but not the account holder, whose identity sits in the exchange's records and can only be reached by a legal request. A bank account is not on a chain at all. These are the points where a person has to ask an institution, and where the work passes from the tracer to the officer.

**What happens at that boundary.** The investigation layer takes over, and it is separate from the tracer:

- **The officer is the one who pauses.** The leads panel says whom to ask (the exchange, the bank, the telecom operator, the token issuer) and what to ask for. The officer approves each letter before it can be sent.
- **A reply adds identifiers, not graph.** What an institution answers (a registered phone, an email, a device, a mule bank account) is added to the case's identifier ledger and opens new leads. The next question follows from the last answer.
- **Banks are not traced through.** The graph shows the on-chain money only. A bank account appears as an identifier and an outcome, with the freeze or lien request it needs, and as a suspected mule. Where the money went after a bank account is only known from what the bank replies.
- **The demo replies are fictional.** The chains of "money moved on to another account" in the demo are invented to show the workflow, and stop after two bank accounts with a cash withdrawal. No real bank data is used or implied.

**What this build does not do yet.**

- It does not follow money through a bank. That needs the bank's records, which only the bank can supply.
- A wallet named in a reply does not start a new trace by itself. An officer would trace it from there as a new step.
- A real reply would have to be entered by the officer, since nothing is received automatically. The demo simulates the reply with a button.

