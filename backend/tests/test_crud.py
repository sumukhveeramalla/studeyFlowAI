from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _future(hours=48):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_seed_present(client):
    r = client.get("/api/courses")
    assert r.status_code == 200
    names = {c["name"] for c in r.json()}
    assert {"Machine Learning", "Data Structures", "Chemistry", "Mathematics"} <= names


def test_assignment_crud_and_persistence(client):
    payload = {
        "title": "Test Assignment",
        "due_at": _future(),
        "priority": "high",
        "estimated_hours": 3,
    }
    r = client.post("/api/assignments", json=payload)
    assert r.status_code == 201
    aid = r.json()["id"]

    # persists on re-fetch
    r = client.get(f"/api/assignments/{aid}")
    assert r.status_code == 200
    assert r.json()["title"] == "Test Assignment"

    # update -> complete sets completed_at
    r = client.put(f"/api/assignments/{aid}", json={"status": "completed"})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert r.json()["completed_at"] is not None

    # delete
    r = client.delete(f"/api/assignments/{aid}")
    assert r.status_code == 204
    r = client.get(f"/api/assignments/{aid}")
    assert r.status_code == 404


def test_task_creation_and_priority(client):
    r = client.post(
        "/api/tasks",
        json={"title": "Read notes", "priority": "high", "estimated_minutes": 45},
    )
    assert r.status_code == 201
    assert r.json()["priority"] == "high"
    assert r.json()["estimated_minutes"] == 45


def test_invalid_assignment_id_on_task(client):
    r = client.post(
        "/api/tasks",
        json={"title": "x", "assignment_id": 99999, "estimated_minutes": 30},
    )
    assert r.status_code == 422


def test_event_validation_error(client):
    start = _future(10)
    r = client.post(
        "/api/events",
        json={"title": "Bad", "kind": "personal", "start_at": start, "end_at": start},
    )
    assert r.status_code == 422


def test_assignment_validation_missing_title(client):
    r = client.post("/api/assignments", json={"due_at": _future()})
    assert r.status_code == 422


def test_preferences_update_applied(client):
    r = client.put("/api/preferences", json={"session_length_min": 60, "break_min": 10})
    assert r.status_code == 200
    assert r.json()["session_length_min"] == 60
    # invalid: end before start
    r = client.put("/api/preferences", json={"study_start_hour": 20, "study_end_hour": 10})
    assert r.status_code == 422


def test_dashboard_reflects_data(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert "stats" in body
    assert body["stats"]["upcoming_assignments"] >= 1
    assert isinstance(body["week_events"], list)
    assert isinstance(body["progress"], list)
