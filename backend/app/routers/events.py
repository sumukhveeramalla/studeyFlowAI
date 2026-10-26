from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import current_user_id
from ..services.timeutil import to_utc

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[schemas.EventOut])
def list_events(db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    return db.scalars(
        select(models.Event).where(models.Event.user_id == uid).order_by(models.Event.start_at)
    ).all()


@router.post("", response_model=schemas.EventOut, status_code=201)
def create_event(
    payload: schemas.EventCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    data = payload.model_dump()
    data["start_at"] = to_utc(data["start_at"])
    data["end_at"] = to_utc(data["end_at"])
    if data["end_at"] <= data["start_at"]:
        raise HTTPException(422, "Event end must be after start")
    event = models.Event(user_id=uid, **data)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{event_id}", response_model=schemas.EventOut)
def get_event(event_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    e = db.get(models.Event, event_id)
    if not e or e.user_id != uid:
        raise HTTPException(404, "Event not found")
    return e


@router.put("/{event_id}", response_model=schemas.EventOut)
def update_event(
    event_id: int,
    payload: schemas.EventUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    e = db.get(models.Event, event_id)
    if not e or e.user_id != uid:
        raise HTTPException(404, "Event not found")
    updates = payload.model_dump(exclude_unset=True)
    for key in ("start_at", "end_at"):
        if key in updates and updates[key] is not None:
            updates[key] = to_utc(updates[key])
    for k, v in updates.items():
        setattr(e, k, v)
    if e.end_at <= e.start_at:
        raise HTTPException(422, "Event end must be after start")
    db.commit()
    db.refresh(e)
    return e


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    e = db.get(models.Event, event_id)
    if not e or e.user_id != uid:
        raise HTTPException(404, "Event not found")
    db.delete(e)
    db.commit()
