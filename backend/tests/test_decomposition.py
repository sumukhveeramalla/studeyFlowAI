from __future__ import annotations

from app.services.decomposition import decompose


def test_decompose_minutes_sum_matches_estimate():
    subtasks = decompose("ML coding project", "implement a model", 4.0, "high")
    assert 3 <= len(subtasks) <= 6
    total = sum(s.estimated_minutes for s in subtasks)
    assert abs(total - int(4.0 * 60)) <= 1  # reconciled to estimate
    # ordered
    assert [s.order_index for s in subtasks] == list(range(len(subtasks)))
    # priority preserved
    assert all(s.priority == "high" for s in subtasks)


def test_decompose_schema_fields():
    subtasks = decompose("History essay", "write a paper", 3.0, "medium")
    for s in subtasks:
        assert s.title
        assert s.estimated_minutes >= 15
        assert s.priority in ("low", "medium", "high")


def test_decompose_endpoint_persists(client):
    # find ML assignment
    aid = next(
        a["id"] for a in client.get("/api/assignments").json()
        if "Data Structures" in a["title"]
    )
    r = client.post(f"/api/assignments/{aid}/decompose")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] in ("llm", "demo")
    assert len(body["tasks"]) >= 3
    # tasks persisted and linked to the assignment
    tasks = client.get("/api/tasks").json()
    linked = [t for t in tasks if t["assignment_id"] == aid]
    assert len(linked) >= 3
