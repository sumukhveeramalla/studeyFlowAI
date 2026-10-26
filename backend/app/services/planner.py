"""Bridges the DB with the scheduling engine and proposal lifecycle."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from .scheduling import (
    Block,
    Interval,
    Prefs,
    ScheduleResult,
    WorkItem,
    intervals_from_events,
    schedule,
)
from .timeutil import ensure_aware
from .validation import Candidate, VResult, validate_blocks


def get_prefs(db: Session, user_id: int) -> Prefs:
    p = db.scalar(select(models.Preference).where(models.Preference.user_id == user_id))
    if not p:
        return Prefs()
    days = tuple(int(x) for x in p.available_days.split(",") if x.strip() != "")
    return Prefs(
        study_start_hour=p.study_start_hour,
        study_end_hour=p.study_end_hour,
        session_length_min=p.session_length_min,
        break_min=p.break_min,
        available_days=days or (0, 1, 2, 3, 4, 5, 6),
        timezone=p.timezone,
    )


def _fixed_events(db: Session, user_id: int) -> list[models.Event]:
    """All events that block time (everything except generated study blocks)."""
    rows = db.scalars(
        select(models.Event).where(models.Event.user_id == user_id)
    ).all()
    return [e for e in rows if not (e.kind == "study" and e.source == "schedule")]


def _study_blocks(db: Session, user_id: int) -> list[models.Event]:
    rows = db.scalars(
        select(models.Event).where(
            models.Event.user_id == user_id,
            models.Event.kind == "study",
            models.Event.source == "schedule",
        )
    ).all()
    return list(rows)


def build_work_items(db: Session, user_id: int) -> list[WorkItem]:
    """Build scheduling demand from tasks and exam prep without double-counting.

    - Tasks that belong to an assignment represent that assignment's work.
    - Assignments WITHOUT any tasks contribute a single work item.
    - Exams contribute a prep work item based on remaining prep progress.
    """
    items: list[WorkItem] = []

    tasks = db.scalars(
        select(models.Task).where(
            models.Task.user_id == user_id,
            models.Task.status != "completed",
        )
    ).all()
    assignment_ids_with_tasks: set[int] = set()
    for t in tasks:
        if t.assignment_id:
            assignment_ids_with_tasks.add(t.assignment_id)
        deadline = ensure_aware(t.deadline) if t.deadline else None
        if deadline is None and t.assignment_id:
            a = db.get(models.Assignment, t.assignment_id)
            if a:
                deadline = ensure_aware(a.due_at)
        items.append(
            WorkItem(
                label=t.title,
                remaining_minutes=t.estimated_minutes,
                priority=t.priority,
                deadline=deadline,
                task_id=t.id,
                assignment_id=t.assignment_id,
            )
        )

    assignments = db.scalars(
        select(models.Assignment).where(
            models.Assignment.user_id == user_id,
            models.Assignment.status != "completed",
        )
    ).all()
    for a in assignments:
        if a.id in assignment_ids_with_tasks:
            continue  # represented by its tasks already
        items.append(
            WorkItem(
                label=a.title,
                remaining_minutes=int(a.estimated_hours * 60),
                priority=a.priority,
                deadline=ensure_aware(a.due_at),
                assignment_id=a.id,
            )
        )

    exams = db.scalars(
        select(models.Exam).where(models.Exam.user_id == user_id)
    ).all()
    now = datetime.now(timezone.utc)
    for e in exams:
        start = ensure_aware(e.start_at)
        if start <= now:
            continue
        remaining = int(e.prep_hours * 60 * (1 - min(max(e.prep_progress, 0), 1)))
        if remaining <= 0:
            continue
        items.append(
            WorkItem(
                label=f"{e.title} prep",
                remaining_minutes=remaining,
                priority=e.priority,
                deadline=start,
                exam_id=e.id,
            )
        )
    return items


def generate_schedule(db: Session, user_id: int, horizon_days: int = 7) -> ScheduleResult:
    prefs = get_prefs(db, user_id)
    busy = intervals_from_events(_fixed_events(db, user_id))
    items = build_work_items(db, user_id)
    now = datetime.now(timezone.utc)
    return schedule(now, items, busy, prefs, horizon_days)


def replan_schedule(
    db: Session,
    user_id: int,
    new_event: dict | None,
    horizon_days: int = 7,
) -> tuple[ScheduleResult, list[Block], list[int]]:
    """Replan preserving unaffected existing study blocks.

    Returns (result_for_affected, preserved_blocks, removed_block_ids).
    """
    prefs = get_prefs(db, user_id)
    fixed_events = _fixed_events(db, user_id)
    busy = intervals_from_events(fixed_events)

    new_interval: Interval | None = None
    if new_event:
        new_interval = Interval(
            ensure_aware(new_event["start_at"]),
            ensure_aware(new_event["end_at"]),
        )
        busy.append(new_interval)

    existing = _study_blocks(db, user_id)
    preserved: list[Block] = []
    affected_item_keys: dict[tuple, WorkItem] = {}
    removed_ids: list[int] = []

    # Determine which existing study blocks conflict with the new event.
    for b in existing:
        bi = Interval(ensure_aware(b.start_at), ensure_aware(b.end_at))
        conflicts = new_interval is not None and bi.overlaps(new_interval)
        if conflicts:
            removed_ids.append(b.id)
        else:
            preserved.append(
                Block(
                    title=b.title,
                    start_at=bi.start,
                    end_at=bi.end,
                    task_id=b.task_id,
                    assignment_id=b.assignment_id,
                    exam_id=b.exam_id,
                )
            )

    # Preserved blocks become busy so we schedule around them (minimal change).
    busy.extend(Interval(b.start_at, b.end_at) for b in preserved)

    # Recompute demand, subtracting minutes already covered by preserved blocks.
    items = build_work_items(db, user_id)
    covered: dict[tuple, int] = {}
    for b in preserved:
        key = (b.task_id, b.assignment_id, b.exam_id)
        minutes = int((b.end_at - b.start_at).total_seconds() // 60)
        covered[key] = covered.get(key, 0) + minutes

    freed_items: list[WorkItem] = []
    for it in items:
        key = (it.task_id, it.assignment_id, it.exam_id)
        remaining = it.remaining_minutes - covered.get(key, 0)
        if remaining > 0:
            it.remaining_minutes = remaining
            freed_items.append(it)

    now = datetime.now(timezone.utc)
    result = schedule(now, freed_items, busy, prefs, horizon_days)
    return result, preserved, removed_ids


def validate_result(
    db: Session, user_id: int, blocks: list[Block], extra_fixed: Interval | None = None
) -> VResult:
    prefs = get_prefs(db, user_id)
    fixed = intervals_from_events(_fixed_events(db, user_id))
    if extra_fixed:
        fixed.append(extra_fixed)
    candidates = []
    for b in blocks:
        deadline = _deadline_for_block(db, b)
        candidates.append(Candidate(b.title, b.start_at, b.end_at, deadline))
    return validate_blocks(candidates, fixed, prefs)


def _deadline_for_block(db: Session, b: Block) -> datetime | None:
    if b.task_id:
        t = db.get(models.Task, b.task_id)
        if t and t.deadline:
            return ensure_aware(t.deadline)
        if t and t.assignment_id:
            a = db.get(models.Assignment, t.assignment_id)
            if a:
                return ensure_aware(a.due_at)
    if b.assignment_id:
        a = db.get(models.Assignment, b.assignment_id)
        if a:
            return ensure_aware(a.due_at)
    if b.exam_id:
        e = db.get(models.Exam, b.exam_id)
        if e:
            return ensure_aware(e.start_at)
    return None
