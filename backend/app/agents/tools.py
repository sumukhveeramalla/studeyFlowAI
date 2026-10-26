"""LangGraph/LangChain tools wrapping deterministic services.

Each tool is a thin, typed function over a DB session. They are exposed both as
LangChain @tool objects (for LLM tool-calling) and as plain callables used by the
graph nodes so the workflow is testable without an LLM.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..services import planner
from ..services.timeutil import ensure_aware


def get_academic_context(db: Session, user_id: int) -> dict:
    assignments = db.scalars(
        select(models.Assignment).where(models.Assignment.user_id == user_id)
    ).all()
    exams = db.scalars(
        select(models.Exam).where(models.Exam.user_id == user_id)
    ).all()
    tasks = db.scalars(
        select(models.Task).where(models.Task.user_id == user_id)
    ).all()
    now = datetime.now(timezone.utc)
    return {
        "assignments": [
            {
                "id": a.id,
                "title": a.title,
                "due_at": ensure_aware(a.due_at).isoformat(),
                "priority": a.priority,
                "status": a.status,
                "estimated_hours": a.estimated_hours,
            }
            for a in sorted(assignments, key=lambda a: ensure_aware(a.due_at))
        ],
        "exams": [
            {
                "id": e.id,
                "title": e.title,
                "start_at": ensure_aware(e.start_at).isoformat(),
                "priority": e.priority,
                "prep_hours": e.prep_hours,
                "prep_progress": e.prep_progress,
            }
            for e in sorted(exams, key=lambda e: ensure_aware(e.start_at))
        ],
        "open_tasks": [
            {"id": t.id, "title": t.title, "priority": t.priority, "status": t.status}
            for t in tasks
            if t.status != "completed"
        ],
        "now": now.isoformat(),
    }


def list_events(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(
        select(models.Event).where(models.Event.user_id == user_id)
    ).all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "kind": e.kind,
            "start_at": ensure_aware(e.start_at).isoformat(),
            "end_at": ensure_aware(e.end_at).isoformat(),
            "is_fixed": e.is_fixed,
        }
        for e in sorted(rows, key=lambda e: ensure_aware(e.start_at))
    ]


def get_preferences(db: Session, user_id: int) -> dict:
    p = planner.get_prefs(db, user_id)
    return {
        "study_start_hour": p.study_start_hour,
        "study_end_hour": p.study_end_hour,
        "session_length_min": p.session_length_min,
        "break_min": p.break_min,
        "available_days": list(p.available_days),
        "timezone": p.timezone,
    }
