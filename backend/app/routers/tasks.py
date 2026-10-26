from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import current_user_id
from ..services.timeutil import to_utc

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    return db.scalars(
        select(models.Task)
        .where(models.Task.user_id == uid)
        .order_by(models.Task.order_index, models.Task.id)
    ).all()


@router.post("", response_model=schemas.TaskOut, status_code=201)
def create_task(
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    data = payload.model_dump()
    if data.get("deadline"):
        data["deadline"] = to_utc(data["deadline"])
    if data.get("assignment_id"):
        a = db.get(models.Assignment, data["assignment_id"])
        if not a or a.user_id != uid:
            raise HTTPException(422, "Invalid assignment_id")
    task = models.Task(user_id=uid, **data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    t = db.get(models.Task, task_id)
    if not t or t.user_id != uid:
        raise HTTPException(404, "Task not found")
    return t


@router.put("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    t = db.get(models.Task, task_id)
    if not t or t.user_id != uid:
        raise HTTPException(404, "Task not found")
    updates = payload.model_dump(exclude_unset=True)
    if "deadline" in updates and updates["deadline"] is not None:
        updates["deadline"] = to_utc(updates["deadline"])
    if updates.get("status") == "completed" and t.status != "completed":
        t.completed_at = datetime.now(timezone.utc)
    if updates.get("status") and updates["status"] != "completed":
        t.completed_at = None
    for k, v in updates.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    t = db.get(models.Task, task_id)
    if not t or t.user_id != uid:
        raise HTTPException(404, "Task not found")
    db.delete(t)
    db.commit()
