from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import current_user_id
from ..agents.runner import run_chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=schemas.ChatResponse)
def chat(
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db),
    uid: int = Depends(current_user_id),
):
    result = run_chat(db, uid, payload.message, payload.conversation_id)
    run = result.run
    proposal = None
    if run.proposal_id:
        proposal = db.get(models.Proposal, run.proposal_id)
    return schemas.ChatResponse(
        run=run,
        reply=run.reply,
        mode=run.mode,
        intent=run.intent,
        proposal=proposal,
        conversation_id=result.conversation_id,
        awaiting_input=result.awaiting_input,
        created_items=[schemas.CreatedItem(**c) for c in result.created_items],
    )
