from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import current_user_id
from ..services.timeutil import to_utc  # noqa: F401 (kept for symmetry)

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("", response_model=list[schemas.CourseOut])
def list_courses(db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    return db.scalars(
        select(models.Course).where(models.Course.user_id == uid).order_by(models.Course.name)
    ).all()


@router.post("", response_model=schemas.CourseOut, status_code=201)
def create_course(
    payload: schemas.CourseCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    course = models.Course(user_id=uid, **payload.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/{course_id}", response_model=schemas.CourseOut)
def get_course(course_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    course = db.get(models.Course, course_id)
    if not course or course.user_id != uid:
        raise HTTPException(404, "Course not found")
    return course


@router.put("/{course_id}", response_model=schemas.CourseOut)
def update_course(
    course_id: int,
    payload: schemas.CourseUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    course = db.get(models.Course, course_id)
    if not course or course.user_id != uid:
        raise HTTPException(404, "Course not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(course, k, v)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    course = db.get(models.Course, course_id)
    if not course or course.user_id != uid:
        raise HTTPException(404, "Course not found")
    db.delete(course)
    db.commit()
