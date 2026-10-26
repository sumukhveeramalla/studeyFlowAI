"""Dashboard statistics computed from live DB data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from .timeutil import ensure_aware, local_tz
from .planner import get_prefs


def _week_bounds_utc(user_tz: str, ref: datetime, offset_weeks: int = 0):
    tz = local_tz(user_tz)
    local = ref.astimezone(tz) + timedelta(weeks=offset_weeks)
    monday = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    sunday_end = monday + timedelta(days=7)
    return monday.astimezone(timezone.utc), sunday_end.astimezone(timezone.utc)


def build_dashboard(db: Session, user_id: int, week_offset: int = 0) -> dict:
    now = datetime.now(timezone.utc)
    prefs = get_prefs(db, user_id)
    tz_name = prefs.timezone
    week_start, week_end = _week_bounds_utc(tz_name, now, week_offset)

    assignments = db.scalars(
        select(models.Assignment).where(models.Assignment.user_id == user_id)
    ).all()
    exams = db.scalars(
        select(models.Exam).where(models.Exam.user_id == user_id)
    ).all()
    tasks = db.scalars(
        select(models.Task).where(models.Task.user_id == user_id)
    ).all()
    events = db.scalars(
        select(models.Event).where(models.Event.user_id == user_id)
    ).all()

    upcoming_assignments = [
        a for a in assignments
        if a.status != "completed" and ensure_aware(a.due_at) >= now
    ]
    upcoming_exams = [e for e in exams if ensure_aware(e.start_at) >= now]

    # Today's study tasks (events of kind study starting today, local).
    tz = local_tz(tz_name)
    today_local = now.astimezone(tz).date()
    todays_study = [
        e for e in events
        if e.kind == "study" and ensure_aware(e.start_at).astimezone(tz).date() == today_local
    ]

    conflicts_resolved = db.scalar(
        select(models.Proposal).where(
            models.Proposal.user_id == user_id,
            models.Proposal.status == "approved",
        )
    )
    approved_count = len([
        p for p in db.scalars(
            select(models.Proposal).where(
                models.Proposal.user_id == user_id,
                models.Proposal.status == "approved",
            )
        ).all()
    ])

    week_events = [
        e for e in events
        if week_start <= ensure_aware(e.start_at) < week_end
    ]
    week_events.sort(key=lambda e: ensure_aware(e.start_at))

    upcoming_deadlines = sorted(
        upcoming_assignments, key=lambda a: ensure_aware(a.due_at)
    )[:6]

    focus_tasks = sorted(
        [t for t in tasks if t.status != "completed"],
        key=lambda t: (
            ensure_aware(t.deadline) if t.deadline else now + timedelta(days=999),
            {"high": 0, "medium": 1, "low": 2}.get(t.priority, 1),
        ),
    )[:6]

    # Study progress per course (tasks completion) + overall assignments.
    progress = []
    total_tasks = len(tasks)
    done_tasks = len([t for t in tasks if t.status == "completed"])
    progress.append(_progress("Tasks completed", done_tasks, total_tasks))
    total_assign = len(assignments)
    done_assign = len([a for a in assignments if a.status == "completed"])
    progress.append(_progress("Assignments completed", done_assign, total_assign))
    total_prep = sum(e.prep_hours for e in exams)
    done_prep = sum(e.prep_hours * e.prep_progress for e in exams)
    progress.append(
        _progress_float("Exam prep", done_prep, total_prep)
    )

    return {
        "stats": {
            "upcoming_assignments": len(upcoming_assignments),
            "upcoming_exams": len(upcoming_exams),
            "todays_tasks": len(todays_study),
            "conflicts_resolved": approved_count,
        },
        "week_events": week_events,
        "upcoming_deadlines": upcoming_deadlines,
        "focus_tasks": focus_tasks,
        "progress": progress,
    }


def _progress(label: str, completed: int, total: int) -> dict:
    pct = round((completed / total) * 100, 1) if total else 0.0
    return {"label": label, "completed": completed, "total": total, "percent": pct}


def _progress_float(label: str, completed: float, total: float) -> dict:
    pct = round((completed / total) * 100, 1) if total else 0.0
    return {
        "label": label,
        "completed": round(completed),
        "total": round(total),
        "percent": pct,
    }
