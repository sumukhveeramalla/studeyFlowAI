"""Persist confirmed intake drafts and auto-decompose assignments."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models


def _parse(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_drafts(db: Session, user_id: int, drafts: list[dict]) -> list[dict]:
    """Create assignments/exams/tasks. Assignments are auto-decomposed.

    Returns a list of {type, id, title, subtask_count}.
    """
    from ..agents.planner_agent import plan_tasks

    created: list[dict] = []
    for d in drafts:
        itype = d["type"]
        if itype == "assignment":
            a = models.Assignment(
                user_id=user_id,
                title=d["title"],
                description=d.get("description", ""),
                due_at=_parse(d["due_at"]),
                priority=d.get("priority", "medium"),
                status="in_progress",
                estimated_hours=float(d.get("estimated_hours", 2.0)),
                course_id=d.get("course_id"),
            )
            db.add(a)
            db.flush()
            # auto-decompose into subtasks
            subtasks, _mode = plan_tasks(
                a.title, a.description, a.estimated_hours, a.priority
            )
            for i, st in enumerate(subtasks):
                db.add(
                    models.Task(
                        user_id=user_id,
                        assignment_id=a.id,
                        title=st["title"],
                        priority=st.get("priority", a.priority),
                        estimated_minutes=st["estimated_minutes"],
                        deadline=a.due_at,
                        status="not_started",
                        order_index=st.get("order_index", i),
                    )
                )
            created.append(
                {
                    "type": "assignment",
                    "id": a.id,
                    "title": a.title,
                    "subtask_count": len(subtasks),
                }
            )
        elif itype == "exam":
            start = _parse(d["start_at"])
            end = d.get("end_at")
            end_dt = _parse(end) if end else start.replace()  # default 2h below
            if not end:
                from datetime import timedelta

                end_dt = start + timedelta(hours=2)
            e = models.Exam(
                user_id=user_id,
                title=d["title"],
                start_at=start,
                end_at=end_dt,
                topics=d.get("topics", []),
                prep_hours=float(d.get("prep_hours", 6.0)),
                priority=d.get("priority", "high"),
                prep_progress=0.0,
                course_id=d.get("course_id"),
            )
            db.add(e)
            db.flush()
            created.append(
                {"type": "exam", "id": e.id, "title": e.title, "subtask_count": 0}
            )
        elif itype == "task":
            t = models.Task(
                user_id=user_id,
                title=d["title"],
                priority=d.get("priority", "medium"),
                estimated_minutes=int(d.get("estimated_minutes", 60)),
                deadline=_parse(d["deadline"]),
                status="not_started",
                assignment_id=d.get("assignment_id"),
            )
            db.add(t)
            db.flush()
            created.append(
                {"type": "task", "id": t.id, "title": t.title, "subtask_count": 0}
            )
    db.commit()
    return created
