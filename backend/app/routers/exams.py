from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import current_user_id
from ..services.timeutil import to_utc

router = APIRouter(prefix="/api/exams", tags=["exams"])


@router.get("", response_model=list[schemas.ExamOut])
def list_exams(db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    return db.scalars(
        select(models.Exam).where(models.Exam.user_id == uid).order_by(models.Exam.start_at)
    ).all()


@router.post("", response_model=schemas.ExamOut, status_code=201)
def create_exam(
    payload: schemas.ExamCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    data = payload.model_dump()
    data["start_at"] = to_utc(data["start_at"])
    data["end_at"] = to_utc(data["end_at"])
    if data["end_at"] <= data["start_at"]:
        raise HTTPException(422, "Exam end must be after start")
    exam = models.Exam(user_id=uid, **data)
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.get("/{exam_id}", response_model=schemas.ExamOut)
def get_exam(exam_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    e = db.get(models.Exam, exam_id)
    if not e or e.user_id != uid:
        raise HTTPException(404, "Exam not found")
    return e


@router.put("/{exam_id}", response_model=schemas.ExamOut)
def update_exam(
    exam_id: int,
    payload: schemas.ExamUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    e = db.get(models.Exam, exam_id)
    if not e or e.user_id != uid:
        raise HTTPException(404, "Exam not found")
    updates = payload.model_dump(exclude_unset=True)
    for key in ("start_at", "end_at"):
        if key in updates and updates[key] is not None:
            updates[key] = to_utc(updates[key])
    for k, v in updates.items():
        setattr(e, k, v)
    db.commit()
    db.refresh(e)
    return e


@router.delete("/{exam_id}", status_code=204)
def delete_exam(exam_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    e = db.get(models.Exam, exam_id)
    if not e or e.user_id != uid:
        raise HTTPException(404, "Exam not found")
    db.delete(e)
    db.commit()
