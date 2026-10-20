# ChainTrace Contract Pack

This pack fixes the interface between **Person A (engine)** and **Person B (product)** so you can work independently. The API already runs end to end on fictional fixture data. Engineering (the real tracing, attribution and ML) is yours to build; you replace the stub in `backend/engine.py` and the rest keeps working.

> All fixture data is **fictional**: addresses are checksum-valid TRON addresses derived from seed strings, and entities are named "Example Exchange A/B/C", "Example Bridge", "Example Mixer". No real wallet or exchange is represented.

---

## 1. What's in the pack

```
chaintrace-contract/
├── CONTRACT.md
├── backend/
│   ├── contract/schemas.py      # the contract as Pydantic models (single source of truth)
│   ├── engine.py                # THE SEAM: Person A replaces the bodies
│   ├── main.py                  # all API routes, working on fixtures (Person B owns)
│   └── tests/test_contract.py   # keeps the engine honest to the contract
├── data/fixtures/               # JSON for every endpoint + sample PDF
└── tools/gen_fixtures.py        # regenerates and validates the fixtures
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

Check the contract at any time: `cd backend && pytest`.

Regenerate fixtures after a contract change: `python tools/gen_fixtures.py` (it validates every file against the models).

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
| POST | `/api/alerts/simulate` | pushes a demo alert to open streams | B |
| POST | `/api/integrations/ncrp/complaints` | `IntegrationAck` (mock NCRP feed) | B |
| POST | `/api/integrations/sahyog/notice` | `IntegrationAck` (mock SAHYOG) | B |

Full request and response shapes are in `backend/contract/schemas.py` and in the live docs at `/docs`.

## 4. Fixed rules (both sides rely on these)

- **Timestamps:** Unix epoch **seconds**, UTC.
- **Amounts:** token units as floats (`7850.0` = 7,850 USDT), never raw integers with decimals.
- **Node types:** `victim`, `scam_wallet`, `intermediary`, `bridge`, `mixer`, `exchange`, `unknown`.
- **Risk levels:** `Low`, `Medium`, `High`, `Critical`. `risk_score` is 0 to 1. Risk is scored on downstream wallets only: the reported wallet (hop 0) is labeled `Reported` and has `risk: null` and `risk_score: null`, and so do the case-level `risk` fields that mirror it.
- **Case urgency:** `act_now`, `act_soon`, `preserve`, plus `urgency_reasons[]` (the triggers that fired). Set by B in `recommendations.py` from the engine's output (the engine returns `urgency: null`). First match wins: `act_now` = idle funds, funds at a VASP deposit address not yet swept, or last outgoing transaction under 24 hours ago; `act_soon` = VASP identified at confidence 0.70 or higher, amount lost 10,000 or more, or 2 or more linked complaints; `preserve` = everything else. The thresholds are demo placeholders. Recommendation `priority` only orders the panel; the UI shows the urgency badge, not a second scale.
- **Attribution method:** `deterministic` (direct label match) or `heuristic` (sweep/gas inference). Heuristic confidence must stay below 0.90.
- **`source`:** `live`, `cached`, or `simulated`. The UI shows it as a badge.
- **Hop:** `-1` for victims, `0` for the reported wallet, increasing downstream.
- **`idle_balance`:** funds still sitting in a leaf wallet. `summary.idle_funds` must equal the sum over nodes (tested).
- **Every `nearest_vasp` has `evidence[]`** and its `deposit_address` must exist in the graph (tested).

> **Contract v1.1.0 (applied):** `urgency` (`act_now | act_soon | preserve`, nullable) and `urgency_reasons[]` are on `TraceResponse` and `CaseSummary`; the reported wallet's `risk` / `risk_score` are nullable on `Node`, `TraceResponse` and `CaseSummary`. `schemas.py`, `tools/gen_fixtures.py`, the fixtures and the seed traces are regenerated, and the tests cover it. "Linked to 2 or more complaints" counts the *other* complaints in the case's network.

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
- Edit **only** `backend/engine.py` (and new modules it imports, e.g. `chains/`, `tracing.py`, `attribution.py`, `risk.py`).
- Return `TraceResponse` and `WalletRisk` exactly as defined. Keep `pytest` green.
- When the real engine works, `/api/trace` switches from fixture to real automatically. Nothing else changes.

**Person B (product)**
- Build the frontend against `/api/*` today.
- Replace the `TODO(B)` stubs in `main.py` (per-case traces, freeze notice generation, real PDF report, dashboard from real cases).
- Add recommendation rules as a function applied to the engine's output (the `recommendations` field). The same function sets `urgency` and `urgency_reasons`.

**Changing the contract**
1. Tell the other person first.
2. Edit `schemas.py`, bump `CONTRACT_VERSION`.
3. Update `tools/gen_fixtures.py`, run it, run `pytest`.
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
| Alerts replay fixtures | `main.simulate_alert` | Wallet watcher |