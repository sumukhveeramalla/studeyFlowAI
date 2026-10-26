from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..deps import current_user_id
from ..services.stats import build_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=schemas.DashboardOut)
def get_dashboard(
    week_offset: int = 0,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return build_dashboard(db, uid, week_offset)
