from __future__ import annotations


def _chat(client, message, conversation_id=None):
    payload = {"message": message}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    r = client.post("/api/chat", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_intake_asks_for_missing_deadline_then_creates(client):
    # 1) user describes an assignment with no date -> assistant asks for the deadline
    res = _chat(client, "Add a Physics lab report assignment, about 3 hours, high priority")
    assert res["intent"] == "create"
    assert res["awaiting_input"] is True
    assert res["conversation_id"]
    assert "when" in res["reply"].lower() or "due" in res["reply"].lower()
    cid = res["conversation_id"]

    # 2) provide the deadline -> assistant confirms
    res = _chat(client, "next Friday at 5pm", cid)
    assert res["awaiting_input"] is True
    assert res["conversation_id"] == cid
    assert "create" in res["reply"].lower()

    # 3) confirm -> items are created
    res = _chat(client, "yes", cid)
    assert res["awaiting_input"] is False
    assert len(res["created_items"]) == 1
    item = res["created_items"][0]
    assert item["type"] == "assignment"
    assert item["subtask_count"] >= 3  # auto-decomposed

    # assignment persisted
    assignments = client.get("/api/assignments").json()
    created = [a for a in assignments if a["id"] == item["id"]]
    assert created and "physics" in created[0]["title"].lower()

    # subtasks persisted and linked
    tasks = client.get("/api/tasks").json()
    linked = [t for t in tasks if t["assignment_id"] == item["id"]]
    assert len(linked) == item["subtask_count"]


def test_intake_cancel_creates_nothing(client):
    before = len(client.get("/api/assignments").json())
    res = _chat(client, "Create a new assignment called Networking essay due tomorrow")
    cid = res["conversation_id"]
    # if it already has everything it may jump to confirm; cancel either way
    res = _chat(client, "no", cid)
    assert res["awaiting_input"] is False
    after = len(client.get("/api/assignments").json())
    assert after == before


def test_intake_exam_requires_date(client):
    res = _chat(client, "I have a Biology midterm covering genetics")
    assert res["intent"] == "create"
    assert res["awaiting_input"] is True
    # the single parsed item should be an exam asking for its date
    assert "biology" in res["reply"].lower() or "date" in res["reply"].lower()
    cid = res["conversation_id"]
    res = _chat(client, "Monday at 10am", cid)
    assert "create" in res["reply"].lower()
    res = _chat(client, "yes", cid)
    created = res["created_items"]
    assert any(c["type"] == "exam" for c in created)
    exams = client.get("/api/exams").json()
    assert any("biology" in e["title"].lower() for e in exams)


def test_parse_multi_item_paragraph():
    """A single paragraph with several items is split into distinct drafts."""
    from app.services.intake import deterministic_parse

    msg = (
        "I have a Machine Learning assignment due next Friday that will take about "
        "6 hours and is high priority. I also have a Chemistry midterm on Monday "
        "covering stoichiometry and acids, need around 8 hours of prep. Also need "
        "to finish my Data Structures project by next Wednesday, and read chapters "
        "3 and 4 for History by tomorrow night."
    )
    r = deterministic_parse(msg, "America/New_York")
    types = [d["type"] for d in r.drafts]
    # at least 4 items with the right mix
    assert len(r.drafts) >= 4
    assert types.count("exam") >= 1
    assert types.count("assignment") >= 2
    assert types.count("task") >= 1
    # every item got a date from the paragraph
    for d in r.drafts:
        date = d.get("due_at") or d.get("start_at") or d.get("deadline")
        assert date, f"{d['title']} missing a date"
    # the exam captured topics
    exam = next(d for d in r.drafts if d["type"] == "exam")
    assert any("stoichiometry" in t.lower() for t in exam.get("topics", []))


def test_multi_item_paragraph_end_to_end(client):
    """Full chat flow: one paragraph creates several items after confirmation."""
    msg = (
        "Add a Thermodynamics assignment due next Friday worth 4 hours, a "
        "Statistics quiz on Monday, and a task to submit my scholarship form "
        "by tomorrow."
    )
    r = client.post("/api/chat", json={"message": msg}).json()
    assert r["intent"] == "create"
    cid = r["conversation_id"]
    # all required deadlines were given, so it should go straight to confirm
    assert "create" in r["reply"].lower()
    # confirm
    done = client.post("/api/chat", json={"message": "yes", "conversation_id": cid}).json()
    created = done["created_items"]
    assert len(created) >= 3
    kinds = {c["type"] for c in created}
    assert "assignment" in kinds and "exam" in kinds and "task" in kinds
    # persisted across resources
    assert any("thermodynamics" in a["title"].lower() for a in client.get("/api/assignments").json())
    assert any("statistics" in e["title"].lower() for e in client.get("/api/exams").json())


def test_date_parsing_variants():
    from app.services.intake import parse_date
    from datetime import datetime, timezone

    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)  # Thursday
    assert parse_date("tomorrow", "America/New_York", now)
    assert parse_date("next friday", "America/New_York", now)
    assert parse_date("in 3 days", "America/New_York", now)
    assert parse_date("Oct 30", "America/New_York", now)
    assert parse_date("", "America/New_York", now) is None


def test_create_then_schedule_still_works(client):
    # create an assignment via intake
    res = _chat(client, "Add an Algorithms assignment due in 5 days, 4 hours")
    cid = res["conversation_id"]
    if res["awaiting_input"] and "create" not in res["reply"].lower():
        res = _chat(client, "in 5 days", cid)
    res = _chat(client, "yes", cid)
    assert res["created_items"]

    # now ask for a schedule -> should go through the graph and make a proposal
    sched = _chat(client, "create a study plan for this week")
    assert sched["intent"] == "schedule"
    assert sched["proposal"] is not None
