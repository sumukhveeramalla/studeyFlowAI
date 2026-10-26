from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import current_user_id

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


def _get_or_create(db: Session, uid: int) -> models.Preference:
    pref = db.scalar(select(models.Preference).where(models.Preference.user_id == uid))
    if not pref:
        pref = models.Preference(user_id=uid)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


@router.get("", response_model=schemas.PreferenceOut)
def get_preferences(db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    return _get_or_create(db, uid)


@router.put("", response_model=schemas.PreferenceOut)
def update_preferences(
    payload: schemas.PreferenceUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    pref = _get_or_create(db, uid)
    updates = payload.model_dump(exclude_unset=True)
    if "study_end_hour" in updates and "study_start_hour" in updates:
        if updates["study_end_hour"] <= updates["study_start_hour"]:
            raise HTTPException(422, "study_end_hour must be after study_start_hour")
    for k, v in updates.items():
        setattr(pref, k, v)
    if pref.study_end_hour <= pref.study_start_hour:
        raise HTTPException(422, "study_end_hour must be after study_start_hour")
    db.commit()
    db.refresh(pref)
    return pref
