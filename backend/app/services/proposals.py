"""Create, apply and reject schedule proposals (human-in-the-loop)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from .scheduling import Block, Interval
from .timeutil import ensure_aware


def _block_snapshot(e: models.Event) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "kind": e.kind,
        "start_at": ensure_aware(e.start_at).isoformat(),
        "end_at": ensure_aware(e.end_at).isoformat(),
        "task_id": e.task_id,
        "assignment_id": e.assignment_id,
        "exam_id": e.exam_id,
    }


def current_schedule_snapshot(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(
        select(models.Event).where(
            models.Event.user_id == user_id,
            models.Event.kind == "study",
            models.Event.source == "schedule",
        )
    ).all()
    return [_block_snapshot(e) for e in rows]


def create_proposal(
    db: Session,
    user_id: int,
    added: list[Block],
    moved: list[dict],
    removed: list[int],
    reason: str,
    infeasible: list[dict] | None = None,
    new_event: dict | None = None,
) -> models.Proposal:
    """Persist a pending proposal describing a schedule diff."""
    original = current_schedule_snapshot(db, user_id)
    proposed = [b for b in original if b["id"] not in removed]
    proposed = proposed + [
        {
            "id": None,
            "title": b.title,
            "kind": b.kind,
            "start_at": b.start_at.isoformat(),
            "end_at": b.end_at.isoformat(),
            "task_id": b.task_id,
            "assignment_id": b.assignment_id,
            "exam_id": b.exam_id,
        }
        for b in added
    ]
    proposed.sort(key=lambda x: x["start_at"])

    summary = {
        "original": original,
        "proposed": proposed,
        "added_count": len(added),
        "moved_count": len(moved),
        "removed_count": len(removed),
        "infeasible": infeasible or [],
        "new_event": new_event,
    }
    changes = {
        "added": [b.to_dict() for b in added],
        "moved": moved,
        "removed": removed,
    }
    proposal = models.Proposal(
        user_id=user_id,
        status="pending",
        reason=reason,
        summary=summary,
        changes=changes,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


def approve_proposal(db: Session, proposal_id: int) -> models.Proposal:
    proposal = db.get(models.Proposal, proposal_id)
    if not proposal:
        raise ValueError("not_found")
    if proposal.status != "pending":
        raise RuntimeError(f"already_{proposal.status}")

    changes = proposal.changes or {}
    # Persist the optional new fixed event first.
    new_event = (proposal.summary or {}).get("new_event")
    if new_event:
        db.add(
            models.Event(
                user_id=proposal.user_id,
                title=new_event.get("title", "Event"),
                kind=new_event.get("kind", "meeting"),
                start_at=_parse(new_event["start_at"]),
                end_at=_parse(new_event["end_at"]),
                is_fixed=True,
                source="manual",
            )
        )

    # Remove blocks.
    for ev_id in changes.get("removed", []):
        ev = db.get(models.Event, ev_id)
        if ev and ev.user_id == proposal.user_id:
            db.delete(ev)

    # Apply moves.
    for mv in changes.get("moved", []):
        ev = db.get(models.Event, mv.get("id"))
        if ev and ev.user_id == proposal.user_id:
            ev.start_at = _parse(mv["to"]["start_at"])
            ev.end_at = _parse(mv["to"]["end_at"])

    # Add new study blocks.
    for b in changes.get("added", []):
        db.add(
            models.Event(
                user_id=proposal.user_id,
                title=b["title"],
                kind=b.get("kind", "study"),
                start_at=_parse(b["start_at"]),
                end_at=_parse(b["end_at"]),
                is_fixed=False,
                source="schedule",
                task_id=b.get("task_id"),
                assignment_id=b.get("assignment_id"),
                exam_id=b.get("exam_id"),
            )
        )

    proposal.status = "approved"
    proposal.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proposal)
    return proposal


def reject_proposal(db: Session, proposal_id: int) -> models.Proposal:
    proposal = db.get(models.Proposal, proposal_id)
    if not proposal:
        raise ValueError("not_found")
    if proposal.status != "pending":
        raise RuntimeError(f"already_{proposal.status}")
    proposal.status = "rejected"
    proposal.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proposal)
    return proposal


def _parse(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
