from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import current_user_id

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/runs", response_model=list[schemas.AgentRunOut])
def list_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    return db.scalars(
        select(models.AgentRun)
        .where(models.AgentRun.user_id == uid)
        .order_by(models.AgentRun.created_at.desc())
        .limit(limit)
    ).all()


@router.get("/runs/{run_id}", response_model=schemas.AgentRunOut)
def get_run(run_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    run = db.get(models.AgentRun, run_id)
    if not run or run.user_id != uid:
        raise HTTPException(404, "Run not found")
    return run
