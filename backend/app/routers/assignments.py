from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import current_user_id
from ..services import decomposition
from ..services.timeutil import to_utc

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


@router.get("", response_model=list[schemas.AssignmentOut])
def list_assignments(db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    rows = db.scalars(
        select(models.Assignment)
        .where(models.Assignment.user_id == uid)
        .order_by(models.Assignment.due_at)
    ).all()
    return rows


@router.post("", response_model=schemas.AssignmentOut, status_code=201)
def create_assignment(
    payload: schemas.AssignmentCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    data = payload.model_dump()
    data["due_at"] = to_utc(data["due_at"])
    assignment = models.Assignment(user_id=uid, **data)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/{assignment_id}", response_model=schemas.AssignmentOut)
def get_assignment(assignment_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    a = db.get(models.Assignment, assignment_id)
    if not a or a.user_id != uid:
        raise HTTPException(404, "Assignment not found")
    return a


@router.put("/{assignment_id}", response_model=schemas.AssignmentOut)
def update_assignment(
    assignment_id: int,
    payload: schemas.AssignmentUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    a = db.get(models.Assignment, assignment_id)
    if not a or a.user_id != uid:
        raise HTTPException(404, "Assignment not found")
    updates = payload.model_dump(exclude_unset=True)
    if "due_at" in updates and updates["due_at"] is not None:
        updates["due_at"] = to_utc(updates["due_at"])
    if updates.get("status") == "completed" and a.status != "completed":
        a.completed_at = datetime.now(timezone.utc)
    if updates.get("status") and updates["status"] != "completed":
        a.completed_at = None
    for k, v in updates.items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    a = db.get(models.Assignment, assignment_id)
    if not a or a.user_id != uid:
        raise HTTPException(404, "Assignment not found")
    db.delete(a)
    db.commit()


@router.post("/{assignment_id}/decompose", response_model=schemas.DecomposeResult)
def decompose_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    """Generate and persist subtasks for an assignment.

    Uses the LLM-backed planner agent when configured, otherwise the
    deterministic template fallback (mode is reported honestly).
    """
    a = db.get(models.Assignment, assignment_id)
    if not a or a.user_id != uid:
        raise HTTPException(404, "Assignment not found")

    from ..agents.planner_agent import plan_tasks

    subtasks, mode = plan_tasks(a.title, a.description, a.estimated_hours, a.priority)

    created: list[models.Task] = []
    for st in subtasks:
        task = models.Task(
            user_id=uid,
            assignment_id=a.id,
            title=st["title"],
            priority=st.get("priority", a.priority),
            estimated_minutes=st["estimated_minutes"],
            deadline=a.due_at,
            status="not_started",
            order_index=st.get("order_index", len(created)),
        )
        db.add(task)
        created.append(task)
    if a.status == "not_started":
        a.status = "in_progress"
    db.commit()
    for t in created:
        db.refresh(t)
    return schemas.DecomposeResult(assignment_id=a.id, mode=mode, tasks=created)
