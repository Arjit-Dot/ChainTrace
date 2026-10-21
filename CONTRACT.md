# ChainTrace Contract Pack

This pack fixes the interface between **Person A (engine)** and **Person B (product)** so you can work independently. The API already runs end to end on fictional fixture data. Engineering (the real tracing, attribution and ML) is yours to build; you replace the stub in `backend/engine/__init__.py` and the rest keeps working.

> All fixture data is **fictional**: addresses are checksum-valid TRON addresses derived from seed strings, and entities are named "Example Exchange A/B/C", "Example Bridge", "Example Mixer". No real wallet or exchange is represented.

---

## 1. What's in the pack

```
chaintrace/
├── CONTRACT.md
├── backend/
│   ├── contract/schemas.py            # the contract as Pydantic models (single source of truth)
│   ├── engine/__init__.py             # THE SEAM: Person A owns (the rest of engine/ is A's too)
│   ├── main.py                        # all API routes (Person B owns); B's code is in backend/product/
│   ├── paths.py                       # where every data file lives
│   └── tests/contract/test_contract.py   # keeps the engine honest to the contract
├── data/fixtures/                     # JSON for every endpoint + sample PDF
└── data/scripts/gen_fixtures.py       # regenerates and validates the fixtures
```

## 2. Run it (this is the "deployment" step)

```bash
# backend (Python 3.12), from the repo root
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --port 8000
# open http://localhost:8000/docs
```

Frontend: your Vite config already proxies `/api` to `http://localhost:8000`, so the UI can call `/api/...` immediately.

Check the contract at any time: `pytest` from the repo root (or from `backend/`).

Regenerate fixtures after a contract change: `python data/scripts/gen_fixtures.py` (it validates every file against the models).

---

## 3. Endpoints

| Method | Path | Returns | Owner |
|---|---|---|---|
| POST | `/api/trace` | `TraceResponse` | A (engine) via B (route) |
| GET | `/api/wallets/{address}/risk` | `WalletRisk` | A |
| GET | `/api/cases` | `CaseSummary[]` | B |
| GET | `/api/cases/{case_id}` | `TraceResponse` | B |
| GET | `/api/cases/{case_id}/freeze-notice` | `FreezeNotice` | B |
| GET | `/api/cases/{case_id}/report` | PDF | B |
| GET | `/api/dashboard` | `DashboardStats` | B |
| GET | `/api/networks` | `Network[]` | B |
| GET | `/api/alerts` | `Alert[]` (history) | B |
| GET | `/api/alerts/stream` | SSE, event name `alert`, data = `Alert` JSON | B |
| POST | `/api/complaints` | `ComplaintReceipt` (201). A citizen files a complaint: a random complaint ID is issued and nothing is traced | B |
| GET | `/api/complaints/{id}/status` | `ComplaintStatusView`: the coarse stage and generic messages only; rate limited; 404 for an unknown ID | B |
| GET | `/api/officer/complaints[?stage=]` | `Complaint[]`: the officer inbox, newest first | B |
| GET | `/api/officer/complaints/{id}` | `Complaint` (full, with the officers-only history) | B |
| POST | `/api/officer/complaints/{id}/review` | `Complaint`: received to under review (409 if not received) | B |
| POST | `/api/officer/complaints/{id}/trace` | `Complaint`: triggers the trace, creates the case, links `case_id`, stage to investigating (409 if already traced) | B |
| GET | `/api/officer/cases/{id}/identifiers` | `Identifier[]`: the case's ledger (wallets, bank accounts, UPI IDs, phones, handles, domains, apps) | B |
| POST | `/api/officer/cases/{id}/identifiers` | `Identifier` (201): an officer adds one by hand; 409 if already there | B |
| GET | `/api/officer/cases/{id}/leads` | `Lead[]`: for each identifier, the institution that holds the identity behind it and the requests to send (suggestions only) | B |
| POST | `/api/alerts/simulate` | pushes a demo alert to open streams | B |
| POST | `/api/cases/{case_id}/simulate-movement` | `Alert[]`: replays a recorded movement of the case's idle funds (SIMULATED), re-checks the case now; 404 if there is none | B |
| POST | `/api/integrations/ncrp/complaints` | `IntegrationAck` (mock NCRP feed) | B |
| POST | `/api/integrations/sahyog/notice` | `IntegrationAck` (mock SAHYOG) | B |

Full request and response shapes are in `backend/contract/schemas.py` and in the live docs at `/docs`.

## 4. Fixed rules (both sides rely on these)

- **Timestamps:** Unix epoch **seconds**, UTC.
- **Amounts:** token units as floats (`7850.0` = 7,850 USDT), never raw integers with decimals.
- **Node types:** `victim`, `scam_wallet`, `intermediary`, `bridge`, `mixer`, `exchange`, `unknown`.
- **Risk levels:** `Low`, `Medium`, `High`, `Critical`. `risk_score` is 0 to 1. Risk is scored on downstream wallets only: the reported wallet (hop 0) is labeled `Reported` and has `risk: null` and `risk_score: null`, and so do the case-level `risk` fields that mirror it.
- **Case urgency:** `act_now`, `act_soon`, `preserve`, plus `urgency_reasons[]` (the triggers that fired). Set by B in `recommendations.py` from the engine's output (the engine returns `urgency: null`). First match wins: `act_now` = idle funds at the last check, funds at a VASP deposit address not yet swept, or a fresh outgoing transfer was observed from a case wallet in the last 15 minutes; `act_soon` = VASP identified at confidence 0.70 or higher, amount lost 10,000 or more, or 2 or more linked complaints; `preserve` = everything else. The thresholds are demo placeholders. Recommendation `priority` only orders the panel; the UI shows the urgency badge, not a second scale.
- **Attribution method:** `deterministic` (direct label match) or `heuristic` (sweep/gas inference). Heuristic confidence must stay below 0.90.
- **`source`:** `live`, `cached`, or `simulated`. The UI shows it as a badge.
- **Hop:** `-1` for victims, `0` for the reported wallet, increasing downstream.
- **`idle_balance`:** funds still sitting in a leaf wallet. `summary.idle_funds` must equal the sum over nodes (tested).
- **Every `nearest_vasp` has `evidence[]`** and its `deposit_address` must exist in the graph (tested).

> **Contract v1.2.0 (in progress):** adds the complaint models (`ComplaintRequest`, `Complaint`, `ComplaintEvent`, `ComplaintReceipt`, `ComplaintStatusView`, `ComplaintTimelineItem`, stages `received`, `under_review`, `investigating`, `action_initiated`, `closed`) and the alert type `COMPLAINT_RECEIVED`; `Alert.case_id` is now optional and `Alert.complaint_id` is new. **What a citizen may see is only `ComplaintStatusView`**: the stage, a fixed sentence per stage and the stage times. Never the wallet, amount, exchange, case or how the complaint is handled. The node types `dex` and `bank_account` are added (the tracer starts producing them in a later stage). **Investigation:** `ComplaintRequest` gains optional lure channels (`scammer_phone`, `scammer_handle` and its platform, `scam_website`, `scam_app`, `paid_to_upi`, `paid_to_bank_account`, `paid_to_ifsc`); a case keeps a ledger of `Identifier`s and derives `Lead`s (choke points: exchange, bank, payment app, P2P desk, telecom, messaging platform, domain and hosting, app store, token issuer). Leads are computed from the ledger, never stored. Citizens never see any of it.

> **Contract v1.1.0 (applied):** `urgency` (`act_now | act_soon | preserve`, nullable) and `urgency_reasons[]` are on `TraceResponse` and `CaseSummary`; the reported wallet's `risk` / `risk_score` are nullable on `Node`, `TraceResponse` and `CaseSummary`. Live monitoring adds `urgency_as_of` and `monitoring` (`Monitoring`) to the same two models and alert type `URGENCY_CHANGED`. `schemas.py`, `data/scripts/gen_fixtures.py`, the fixtures and the seed traces are regenerated, and the tests cover it. "Linked to 2 or more complaints" counts the *other* complaints in the case's network.

**Live monitoring (v1.1.0).** B's watcher (`alerts.py`) polls the leaf and idle wallets of every case (placeholder: every 30 seconds) and re-evaluates urgency on each poll.
- `urgency_as_of` (epoch seconds): the time of the last successful chain check, not of the last change, so a quiet case still shows a fresh time.
- `monitoring`: `{status: live | stale | off, last_checked_at, poll_interval_sec}`. `stale` means the last check is older than about twice the poll interval, so the badge cannot claim freshness it does not have. B derives it when a case is read; the engine returns `monitoring: null`.
- Third `act_now` trigger: a fresh outgoing transfer observed from a case wallet in the last 15 minutes (placeholder).
- Alert type `URGENCY_CHANGED`: the message carries the old and new level. Urgency can go down as well as up.
- Seam function, next to `trace_complaint`: `new_transfers(addresses, since_ts) -> list[Transfer]`. It lets the watcher poll a few wallets without a full re-trace; a full re-trace runs only when a wallet actually moved. The seam is otherwise fixed, so this addition went through the change process in section 6.
- Limits: "live" means polling (a delay of up to one poll interval plus block confirmation time); only leaf and idle wallets are watched because of API rate limits; monitoring improves how current the reading is, it cannot make `act_now` mean a freeze will succeed.

Suggested UI colors per node type: victim grey, scam_wallet red, intermediary orange, bridge blue, mixer purple, exchange green, unknown white.

## 5. The hero fixture, in one picture

```
 Victim1,2,3 ──► REPORTED WALLET
                     ├─► Pass-through 1 ─┬─► Deposit addr (Example Exchange A) ──► Hot wallet     [Nearest VASP, 87% heuristic]
                     │                   └─► Example Mixer (50 USDT)
                     └─► Pass-through 2 ───► Example Bridge ──► Ethereum wallet (3,720 USDT idle) [idle funds: act_now]
```

It exercises every feature of the demo: pass-through detection, exchange attribution with evidence, cross-chain bridge, mixer, idle funds, and four recommendation priorities.

Other fixtures: 8 cases (two networks, one unresolved ransomware case, one still tracing), dashboard stats, 2 networks, 4 alerts, a drafted freeze notice, mock NCRP/SAHYOG acknowledgments.

---

## 6. Who changes what

**Person A (engine)**
- Edit **only** `backend/engine/__init__.py` (the `backend/engine/` package: `chains/`, `trace/`, `model/`).
- Return `TraceResponse` and `WalletRisk` exactly as defined. Keep `pytest` green.
- When the real engine works, `/api/trace` switches from fixture to real automatically. Nothing else changes.

**Person B (product)**
- Build the frontend against `/api/*` today.
- Replace the `TODO(B)` stubs in `main.py` (per-case traces, freeze notice generation, real PDF report, dashboard from real cases).
- Add recommendation rules as a function applied to the engine's output (the `recommendations` field). The same function sets `urgency` and `urgency_reasons`.

**Changing the contract**
1. Tell the other person first.
2. Edit `schemas.py`, bump `CONTRACT_VERSION`.
3. Update `data/scripts/gen_fixtures.py`, run it, run `pytest`.
4. Merge together.

---

## 7. Known stubs (intentionally left for engineering)

| Stub | Where | Real version |
|---|---|---|
| Trace for any wallet returns the hero case with your IDs swapped in | `engine.trace_complaint` | Chain adapter, tracing, attribution |
| Risk for any wallet returns the hero risk | `engine.wallet_risk` | Feature extraction + model + SHAP |
| `/api/cases/{id}` returns the hero trace | `main.get_case` | Stored trace per case |
| Freeze notice and PDF are samples | `main.freeze_notice`, `main.report` | Template fill + ReportLab |
| Dashboard and networks are static | `main.dashboard`, `main.networks` | Computed from stored cases |
| Live monitoring feed is a recorded replay (SIMULATED) | `engine.release_replay`, `main.simulate_movement` | `engine.new_transfers` against TronGrid with a key (the watcher in `alerts.py` is already real) |