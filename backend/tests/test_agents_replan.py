from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")


def _tomorrow_local(h, m=0):
    day = (datetime.now(TZ) + timedelta(days=1)).date()
    return datetime.combine(day, time(h, m), tzinfo=TZ).astimezone(timezone.utc)


def test_generate_schedule_creates_proposal(client):
    r = client.post("/api/schedule/generate", json={"horizon_days": 7})
    assert r.status_code == 200
    p = r.json()
    assert p["status"] == "pending"
    assert "proposed" in p["summary"]


def test_chat_query_intent(client):
    r = client.post("/api/chat", json={"message": "Show my upcoming deadlines"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "query"
    assert body["reply"]
    assert any(s["agent"] == "academic" for s in body["run"]["steps"])


def test_chat_decompose_intent(client):
    r = client.post(
        "/api/chat", json={"message": "Break down my Machine Learning assignment"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "decompose"
    assert any(s["tool"] == "decompose_assignment" for s in body["run"]["steps"])


def test_full_replanning_demo_smoke(client):
    """End-to-end: seeded study session tomorrow 9-11am conflicts with a new
    meeting; replan -> proposal -> approve -> schedule persists & conflict gone."""
    # confirm the seeded study block exists tomorrow morning
    events_before = client.get("/api/events").json()
    study_blocks_before = [
        e for e in events_before if e["kind"] == "study" and e["source"] == "schedule"
    ]
    assert study_blocks_before, "expected a seeded study block"

    # Ask the agent to replan around an unexpected meeting tomorrow 9-11am.
    r = client.post(
        "/api/chat",
        json={
            "message": "I have an unexpected meeting tomorrow from 9 AM to 11 AM. "
            "Rearrange my study schedule without missing deadlines."
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "replan"
    steps = body["run"]["steps"]
    assert any(s["agent"] == "replanner" for s in steps)
    assert any(s["agent"] == "validator" for s in steps)
    assert body["proposal"] is not None
    proposal_id = body["proposal"]["id"]

    changes = body["proposal"]["changes"]
    # the conflicting 9-11 block should be slated for removal
    assert len(changes["removed"]) >= 1

    # Approve -> schedule changes apply
    r = client.post(f"/api/proposals/{proposal_id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    # The new meeting now exists and nothing overlaps it.
    events_after = client.get("/api/events").json()
    meeting = [e for e in events_after if e["kind"] == "meeting"]
    assert meeting, "approved meeting should be persisted"
    m = meeting[0]
    m_start = datetime.fromisoformat(m["start_at"])
    m_end = datetime.fromisoformat(m["end_at"])
    for e in events_after:
        if e["kind"] == "study" and e["source"] == "schedule":
            s = datetime.fromisoformat(e["start_at"])
            en = datetime.fromisoformat(e["end_at"])
            assert not (s < m_end and m_start < en), "study block overlaps new meeting"


def test_reject_proposal_has_no_effect(client):
    events_before = client.get("/api/events").json()
    r = client.post("/api/schedule/generate", json={"horizon_days": 7})
    pid = r.json()["id"]
    r = client.post(f"/api/proposals/{pid}/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    # cannot decide twice
    r = client.post(f"/api/proposals/{pid}/approve")
    assert r.status_code == 409
    # events unchanged in count
    events_after = client.get("/api/events").json()
    assert len(events_after) == len(events_before)


def test_agent_runs_history(client):
    client.post("/api/chat", json={"message": "prioritize my tasks"})
    r = client.get("/api/agents/runs")
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert r.json()[0]["steps"]
