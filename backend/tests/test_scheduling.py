from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.services.scheduling import Interval, Prefs, WorkItem, schedule
from app.services.validation import Candidate, validate_blocks

TZ = ZoneInfo("America/New_York")


def _local(day, h, m=0):
    return datetime.combine(day, time(h, m), tzinfo=TZ).astimezone(timezone.utc)


def test_overlap_detection():
    day = (datetime.now(TZ) + timedelta(days=1)).date()
    a = Candidate("A", _local(day, 9), _local(day, 11))
    b = Candidate("B", _local(day, 10), _local(day, 12))
    res = validate_blocks([a, b], [], Prefs(timezone="America/New_York"))
    assert not res.ok
    assert any(e.code == "block_overlap" for e in res.errors)


def test_fixed_conflict_detection():
    day = (datetime.now(TZ) + timedelta(days=1)).date()
    block = Candidate("Study", _local(day, 13), _local(day, 14))
    fixed = [Interval(_local(day, 13), _local(day, 15))]
    res = validate_blocks([block], fixed, Prefs(timezone="America/New_York"))
    assert not res.ok
    assert any(e.code == "fixed_conflict" for e in res.errors)


def test_deadline_violation():
    day = (datetime.now(TZ) + timedelta(days=1)).date()
    deadline = _local(day, 10)
    block = Candidate("Late", _local(day, 11), _local(day, 12), deadline=deadline)
    res = validate_blocks([block], [], Prefs(timezone="America/New_York"))
    assert not res.ok
    assert any(e.code == "deadline_violation" for e in res.errors)


def test_schedule_respects_fixed_and_no_overlap():
    now = datetime.now(timezone.utc)
    day = (now.astimezone(TZ) + timedelta(days=1)).date()
    prefs = Prefs(timezone="America/New_York", session_length_min=60, break_min=15)
    busy = [Interval(_local(day, 13), _local(day, 15))]  # fixed class 1-3pm
    items = [
        WorkItem("ML HW", 120, "high", _local(day, 21)),
    ]
    res = schedule(now, items, busy, prefs, horizon_days=3)
    assert res.blocks, "expected study blocks"
    # none overlap the fixed class
    fixed = busy[0]
    for b in res.blocks:
        assert not Interval(b.start_at, b.end_at).overlaps(fixed)
    # blocks don't overlap each other
    ordered = sorted(res.blocks, key=lambda b: b.start_at)
    for x, y in zip(ordered, ordered[1:]):
        assert x.end_at <= y.start_at


def test_schedule_infeasible_reports_shortfall():
    now = datetime.now(timezone.utc)
    day = (now.astimezone(TZ) + timedelta(days=1)).date()
    prefs = Prefs(timezone="America/New_York")
    # deadline too soon for 10 hours of work
    deadline = _local(day, 10)
    items = [WorkItem("Huge", 600, "high", deadline)]
    res = schedule(now, items, [], prefs, horizon_days=3)
    assert res.infeasible
    assert res.infeasible[0].placed_minutes < res.infeasible[0].needed_minutes


def test_schedule_before_deadline():
    now = datetime.now(timezone.utc)
    day2 = (now.astimezone(TZ) + timedelta(days=2)).date()
    prefs = Prefs(timezone="America/New_York", session_length_min=90, break_min=15)
    deadline = _local(day2, 17)
    items = [WorkItem("PSet", 90, "medium", deadline)]
    res = schedule(now, items, [], prefs, horizon_days=4)
    assert res.blocks
    for b in res.blocks:
        assert b.end_at <= deadline
