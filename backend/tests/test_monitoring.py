"""Live monitoring (B6 + the engine's new_transfers): as-of, stale, watchlist, re-evaluation, alerts, replay."""
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import alerts
import engine
import engine_client
import store
from contract.schemas import Alert, CaseSummary, TraceResponse

ROOT = Path(__file__).resolve().parents[2]
IDLE = next(s for s in json.loads((ROOT / "data" / "scenarios.json").read_text()) if s["key"] == "idle")


@pytest.fixture
def client(tmp_path, monkeypatch):
    import main
    monkeypatch.setenv("CHAINTRACE_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("ENGINE_MODE", "engine")
    monkeypatch.setenv("CHAINTRACE_MONITOR", "1")
    engine.reset_replay()
    alerts._live.clear()
    with TestClient(main.app) as c:
        yield c
    engine.reset_replay()


def submit(client):
    return client.post("/api/trace", json={"complaint_id": "MON-1", "wallet": IDLE["wallet"],
                                           "amount": IDLE["amount"], "fraud_type": "investment"}).json()


# ---- seam: new_transfers and the replay
def test_new_transfers_is_quiet_until_a_replay_is_released():
    nodes = engine.trace_complaint(engine_request()).graph.nodes
    addrs = [n.id for n in nodes if n.hop >= 1]
    assert engine.new_transfers(addrs, int(time.time())) == []
    assert engine.release_replay(addrs[-1]) == 1 and engine.release_replay(addrs[-1]) == 0
    moved = engine.new_transfers(addrs, int(time.time()))
    assert len(moved) == 1 and moved[0].amount == 5880.0
    assert engine.new_transfers(addrs, int(time.time())) == []        # delivered once
    engine.reset_replay()


def engine_request():
    from contract.schemas import TraceRequest
    return TraceRequest(complaint_id="X", wallet=IDLE["wallet"], amount=IDLE["amount"])


# ---- stamps, stale, watchlist
def test_new_case_is_live_with_an_as_of_time(client):
    t = submit(client)
    assert t["monitoring"]["status"] == "live" and t["monitoring"]["poll_interval_sec"] == 30
    assert abs(t["urgency_as_of"] - time.time()) < 5 and t["monitoring"]["last_checked_at"] == t["urgency_as_of"]
    case = client.get("/api/cases").json()[0]
    assert case["urgency_as_of"] == t["urgency_as_of"] and case["monitoring"]["status"] == "live"


def test_stale_when_last_check_is_older_than_twice_the_interval(client):
    t = TraceResponse(**submit(client))
    assert store._aged(t, now=t.urgency_as_of + 59).monitoring.status == "live"
    assert store._aged(t, now=t.urgency_as_of + 61).monitoring.status == "stale"
    off = t.model_copy(update={"monitoring": t.monitoring.model_copy(update={"status": "off"})})
    assert store._aged(off, now=t.urgency_as_of + 999).monitoring.status == "off"


def test_monitoring_off_when_watcher_disabled(client, monkeypatch):
    monkeypatch.setenv("CHAINTRACE_MONITOR", "0")
    assert submit(client)["monitoring"]["status"] == "off"


def test_watchlist_is_leaf_and_idle_wallets_only(client):
    t = TraceResponse(**submit(client))
    assert set(alerts.watchlist(t)) == {n.id for n in t.graph.nodes if n.idle_balance > 0}
    hero = TraceResponse(**json.loads((ROOT / "data" / "fixtures" / "trace_hero.json").read_text()))
    watched = {n.id: n for n in hero.graph.nodes}
    assert all(watched[a].type in ("scam_wallet", "intermediary", "unknown") for a in alerts.watchlist(hero))


# ---- polling
def test_quiet_poll_refreshes_as_of_without_alerts(client):
    t = submit(client)
    later = t["urgency_as_of"] + 20
    assert alerts.poll_case(t["case_id"], now=later) == []
    again = client.get(f"/api/cases/{t['case_id']}").json()
    assert again["urgency_as_of"] == later and again["urgency"] == t["urgency"] == "act_now"


def test_failed_check_changes_nothing_so_the_case_goes_stale(client, monkeypatch):
    t = submit(client)

    def boom(*a, **k):
        raise RuntimeError("chain API down")
    monkeypatch.setattr(engine_client, "new_transfers", boom)
    assert alerts.poll_case(t["case_id"], now=t["urgency_as_of"] + 500) == []
    assert store.get_trace(t["case_id"]).urgency_as_of == t["urgency_as_of"]


def test_urgency_can_go_down_when_idle_funds_move(client):
    t = submit(client)
    assert t["urgency"] == "act_now" and t["summary"]["idle_funds"] == 5900.0
    new = client.post(f"/api/cases/{t['case_id']}/simulate-movement")
    assert new.status_code == 200
    types = [a["type"] for a in new.json()]
    assert types == ["FUNDS_MOVED", "REACHED_VASP", "URGENCY_CHANGED"]
    assert "simulated replay" in new.json()[0]["message"]
    assert "Act now to Act soon" in new.json()[2]["message"]

    after = client.get(f"/api/cases/{t['case_id']}").json()
    assert after["urgency"] == "act_soon" and after["summary"]["idle_funds"] == 0.0
    assert after["nearest_vasp"]["vasp"] == "Example Exchange B" and after["urgency_as_of"] >= t["urgency_as_of"]
    case = client.get("/api/cases").json()[0]
    assert case["urgency"] == "act_soon" and case["vasp"] == "Example Exchange B" and case["status"] == "attributed"


def test_alerts_reach_history_and_a_second_replay_is_rejected(client):
    t = submit(client)
    client.post(f"/api/cases/{t['case_id']}/simulate-movement")
    hist = [Alert(**a) for a in client.get("/api/alerts").json()]
    assert hist[0].type == "URGENCY_CHANGED" and hist[0].case_id == t["case_id"]
    assert client.post(f"/api/cases/{t['case_id']}/simulate-movement").status_code == 404
    assert client.post("/api/cases/C-999/simulate-movement").status_code == 404


def test_case_with_no_replay_cannot_simulate(client):
    t = client.post("/api/trace", json={"complaint_id": "H", "wallet": "TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo",
                                        "amount": 12000.0}).json()
    assert client.post(f"/api/cases/{t['case_id']}/simulate-movement").status_code == 404


def test_fixture_mode_never_sees_new_transfers(monkeypatch):
    monkeypatch.setenv("ENGINE_MODE", "fixture")
    assert engine_client.new_transfers(["T1"], 0) == [] and engine_client.release_replay("T1") == 0
