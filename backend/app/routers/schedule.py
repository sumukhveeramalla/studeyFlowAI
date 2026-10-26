from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import current_user_id
from ..services import planner, proposals
from ..services.timeutil import ensure_aware

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.post("/generate", response_model=schemas.ProposalOut)
def generate(
    payload: schemas.GenerateScheduleRequest,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    result = planner.generate_schedule(db, uid, payload.horizon_days)
    validation = planner.validate_result(db, uid, result.blocks)
    reason = result.explanation
    if not validation.ok:
        reason += " (validation flagged issues)"
    # For a fresh generation, all current study blocks are replaced.
    existing = proposals.current_schedule_snapshot(db, uid)
    removed = [b["id"] for b in existing]
    proposal = proposals.create_proposal(
        db, uid,
        added=result.blocks,
        moved=[],
        removed=removed,
        reason=reason,
        infeasible=[i.to_dict() for i in result.infeasible],
    )
    return proposal


@router.post("/replan", response_model=schemas.ProposalOut)
def replan(
    payload: schemas.ReplanRequest,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    new_event = None
    if payload.new_event:
        new_event = {
            "title": payload.new_event.title,
            "kind": payload.new_event.kind,
            "start_at": ensure_aware(payload.new_event.start_at),
            "end_at": ensure_aware(payload.new_event.end_at),
        }

    result, preserved, removed_ids = planner.replan_schedule(
        db, uid, new_event, payload.horizon_days
    )

    # Validate the full proposed set (preserved + new) against fixed events incl. new.
    extra = None
    if new_event:
        from ..services.scheduling import Interval
        extra = Interval(new_event["start_at"], new_event["end_at"])
    all_blocks = preserved + result.blocks
    validation = planner.validate_result(db, uid, all_blocks, extra_fixed=extra)

    reason = result.explanation
    if removed_ids:
        reason = (
            f"Detected {len(removed_ids)} conflicting study block(s); "
            f"rescheduled affected work. " + reason
        )
    if not validation.ok:
        reason += " Validation flagged remaining issues."

    # serialize new_event for storage
    stored_new = None
    if new_event:
        stored_new = {
            "title": new_event["title"],
            "kind": new_event["kind"],
            "start_at": new_event["start_at"].isoformat(),
            "end_at": new_event["end_at"].isoformat(),
        }

    proposal = proposals.create_proposal(
        db, uid,
        added=result.blocks,
        moved=[],
        removed=removed_ids,
        reason=reason,
        infeasible=[i.to_dict() for i in result.infeasible],
        new_event=stored_new,
    )
    return proposal


@router.post("/validate", response_model=schemas.ValidationResult)
def validate(
    payload: schemas.ValidateRequest,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    from ..services.scheduling import Block
    blocks = [
        Block(
            title=b.title,
            start_at=ensure_aware(b.start_at),
            end_at=ensure_aware(b.end_at),
            task_id=b.task_id,
            assignment_id=b.assignment_id,
            exam_id=b.exam_id,
        )
        for b in payload.events
    ]
    result = planner.validate_result(db, uid, blocks)
    return schemas.ValidationResult(
        ok=result.ok,
        errors=[schemas.ValidationError(**e.to_dict()) for e in result.errors],
    )


# ---- Proposals ----
proposal_router = APIRouter(prefix="/api/proposals", tags=["proposals"])


@proposal_router.get("", response_model=list[schemas.ProposalOut])
def list_proposals(db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    return db.scalars(
        select(models.Proposal)
        .where(models.Proposal.user_id == uid)
        .order_by(models.Proposal.created_at.desc())
    ).all()


@proposal_router.get("/{proposal_id}", response_model=schemas.ProposalOut)
def get_proposal(proposal_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    p = db.get(models.Proposal, proposal_id)
    if not p or p.user_id != uid:
        raise HTTPException(404, "Proposal not found")
    return p


@proposal_router.post("/{proposal_id}/approve", response_model=schemas.ProposalOut)
def approve(proposal_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    p = db.get(models.Proposal, proposal_id)
    if not p or p.user_id != uid:
        raise HTTPException(404, "Proposal not found")
    try:
        return proposals.approve_proposal(db, proposal_id)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@proposal_router.post("/{proposal_id}/reject", response_model=schemas.ProposalOut)
def reject(proposal_id: int, db: Session = Depends(get_db), uid: int = Depends(current_user_id)):
    p = db.get(models.Proposal, proposal_id)
    if not p or p.user_id != uid:
        raise HTTPException(404, "Proposal not found")
    try:
        return proposals.reject_proposal(db, proposal_id)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
