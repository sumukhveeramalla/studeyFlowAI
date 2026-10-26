"""Execute the agent workflow for a chat message and persist the run.

Routing:
- If the message belongs to an active intake conversation, or is classified as a
  "create" intent, run the multi-turn intake flow (stateful, human-in-the-loop
  item creation).
- Otherwise run the LangGraph workflow (query / decompose / schedule / replan).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from ..services import intake_flow
from .graph import build_graph
from .llm import llm_available
from .nodes import (
    _UNAMBIGUOUS_SCHEDULE,
    RunContext,
    _keyword_intent,
    _llm_intent,
    set_context,
)
from .state import AgentState


@dataclass
class ChatResult:
    run: models.AgentRun
    conversation_id: Optional[int]
    awaiting_input: bool
    created_items: list[dict]


def _classify(message: str) -> tuple[str, dict, str]:
    mode = "llm" if llm_available() else "demo"
    intent, params = _keyword_intent(message)
    # Don't let the LLM override unambiguous command phrases (e.g.
    # "create a study plan" is scheduling, not item creation).
    low = message.lower()
    locked = (
        (intent == "schedule" and any(p in low for p in _UNAMBIGUOUS_SCHEDULE))
        or (intent == "replan" and any(
            p in low for p in ["unexpected", "reschedule", "replan", "rearrange", "missed"]
        ))
    )
    if mode == "llm" and not locked:
        res = _llm_intent(message)
        if res:
            intent, params = res
    return intent, params, mode


def _active_conversation(db: Session, user_id: int, conversation_id: Optional[int]):
    if not conversation_id:
        return None
    conv = db.get(models.Conversation, conversation_id)
    if conv and conv.user_id == user_id and conv.status not in ("done", "cancelled"):
        return conv
    return None


def run_chat(
    db: Session,
    user_id: int,
    message: str,
    conversation_id: Optional[int] = None,
) -> ChatResult:
    mode = "llm" if llm_available() else "demo"

    active = _active_conversation(db, user_id, conversation_id)
    intent = "create" if active else None
    if intent is None:
        intent, _params, mode = _classify(message)

    # ---- Intake flow (stateful creation) ----
    if intent == "create" or active:
        result = intake_flow.start_or_continue(db, user_id, message, conversation_id)
        run = _persist_run(
            db, user_id, message, intent="create", mode=mode,
            reply=result["reply"], steps=result["steps"],
            status="awaiting_input" if result["awaiting_input"] else "completed",
            proposal_id=None,
        )
        return ChatResult(
            run=run,
            conversation_id=result["conversation_id"],
            awaiting_input=result["awaiting_input"],
            created_items=result["created_items"],
        )

    # ---- LangGraph workflow ----
    set_context(RunContext(db, user_id))
    graph = build_graph()
    initial: AgentState = {
        "user_id": user_id,
        "user_message": message,
        "steps": [],
        "retries": 0,
    }
    try:
        final: AgentState = graph.invoke(initial)
    except Exception as exc:  # graceful degradation
        final = {
            **initial,
            "intent": "error",
            "mode": mode,
            "reply": (
                "Something went wrong while running the agents. "
                "Please try rephrasing your request."
            ),
            "steps": initial.get("steps", [])
            + [{
                "idx": len(initial.get("steps", [])),
                "agent": "supervisor",
                "tool": "error",
                "note": f"Workflow error: {type(exc).__name__}",
                "validation": None,
            }],
        }

    proposal = final.get("proposal")
    run = _persist_run(
        db, user_id, message,
        intent=final.get("intent", ""),
        mode=final.get("mode", mode),
        reply=final.get("reply", ""),
        steps=final.get("steps", []),
        status="awaiting_approval" if proposal else "completed",
        proposal_id=proposal["id"] if proposal else None,
    )
    return ChatResult(
        run=run, conversation_id=None, awaiting_input=False, created_items=[]
    )


def _persist_run(
    db: Session,
    user_id: int,
    message: str,
    intent: str,
    mode: str,
    reply: str,
    steps: list[dict],
    status: str,
    proposal_id: Optional[int],
) -> models.AgentRun:
    run = models.AgentRun(
        user_id=user_id,
        user_message=message,
        intent=intent,
        status=status,
        mode=mode,
        reply=reply,
        proposal_id=proposal_id,
    )
    db.add(run)
    db.flush()
    for i, s in enumerate(steps):
        db.add(
            models.AgentStep(
                run_id=run.id,
                idx=s.get("idx", i),
                agent=s["agent"],
                tool=s.get("tool", ""),
                note=s.get("note", ""),
                validation=s.get("validation"),
            )
        )
    db.commit()
    db.refresh(run)
    return run
