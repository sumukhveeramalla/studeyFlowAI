"""Multi-turn intake orchestrator (human-in-the-loop item creation).

State machine over a Conversation row:
  gathering  -> ask for the next missing required field, or move to confirming
  confirming -> wait for yes/no; yes creates items, no cancels
  done / cancelled -> terminal

Returns a dict the runner turns into a ChatResponse:
  {reply, steps, awaiting_input, conversation_id, created_items, done}
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .. import models
from . import intake
from .intake_create import create_drafts
from .planner import get_prefs


def _tz(db: Session, user_id: int) -> str:
    return get_prefs(db, user_id).timezone


def _step(agent: str, tool: str, note: str) -> dict:
    return {"agent": agent, "tool": tool, "note": note, "validation": None}


def start_or_continue(
    db: Session,
    user_id: int,
    message: str,
    conversation_id: Optional[int],
) -> dict:
    tz = _tz(db, user_id)
    steps: list[dict] = []

    conv: Optional[models.Conversation] = None
    if conversation_id:
        conv = db.get(models.Conversation, conversation_id)
        if conv and (conv.user_id != user_id or conv.status in ("done", "cancelled")):
            conv = None

    # ---- New conversation: parse the message into drafts ----
    if conv is None:
        result = intake.llm_parse(message, tz)
        mode = "llm"
        if result is None:
            result = intake.deterministic_parse(message, tz)
            mode = "demo"
        steps.append(
            _step("intake", "parse_items",
                  f"Parsed {len(result.drafts)} item(s) from the message (mode={mode}).")
        )
        if not result.drafts:
            return {
                "reply": (
                    "I can create assignments, exams and tasks for you. Tell me what "
                    "you have — for example: \"ML assignment due next Friday, ~6 hours, "
                    "and a Chemistry midterm on Monday\"."
                ),
                "steps": steps,
                "awaiting_input": True,
                "conversation_id": None,
                "created_items": [],
                "done": False,
            }
        conv = models.Conversation(
            user_id=user_id,
            status="gathering",
            drafts=result.drafts,
            active_index=0,
            pending_field=None,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
    else:
        # ---- Continuing: apply the user's answer ----
        if conv.status == "confirming":
            if intake.is_affirmative(message):
                return _do_create(db, user_id, conv, steps, tz)
            if intake.is_negative(message):
                conv.status = "cancelled"
                db.commit()
                steps.append(_step("intake", "cancel", "User cancelled the intake."))
                return {
                    "reply": "No problem — I won't create anything. Tell me when you're ready.",
                    "steps": steps,
                    "awaiting_input": False,
                    "conversation_id": conv.id,
                    "created_items": [],
                    "done": True,
                }
            # ambiguous reply during confirmation: re-ask
            steps.append(_step("intake", "confirm", "Awaiting a yes/no confirmation."))
            return {
                "reply": _confirm_text(conv, tz) + "\n\nShould I create these? (yes/no)",
                "steps": steps,
                "awaiting_input": True,
                "conversation_id": conv.id,
                "created_items": [],
                "done": False,
            }
        else:
            # gathering: the message answers the pending field (or adds detail)
            drafts = conv.drafts
            idx = conv.active_index
            if 0 <= idx < len(drafts):
                intake.apply_answer_to_draft(drafts[idx], message, tz)
                flag_modified(conv, "drafts")
            steps.append(
                _step("intake", "fill_slot",
                      f"Recorded answer for field '{conv.pending_field}'.")
            )

    # ---- Advance the gathering state machine ----
    return _advance(db, user_id, conv, steps, tz)


def _advance(db: Session, user_id: int, conv: models.Conversation, steps, tz) -> dict:
    drafts = conv.drafts
    # find the first draft with a missing required field
    for i, draft in enumerate(drafts):
        missing = intake.first_missing_field(draft)
        if missing:
            conv.active_index = i
            conv.pending_field = missing
            conv.status = "gathering"
            db.commit()
            steps.append(
                _step("intake", "ask_missing",
                      f"Asking for '{missing}' of {draft['type']} \"{draft.get('title')}\".")
            )
            return {
                "reply": intake.question_for(draft, missing),
                "steps": steps,
                "awaiting_input": True,
                "conversation_id": conv.id,
                "created_items": [],
                "done": False,
            }

    # all complete -> confirm
    conv.status = "confirming"
    conv.pending_field = None
    db.commit()
    steps.append(_step("intake", "confirm", "All required fields gathered; confirming."))
    return {
        "reply": _confirm_text(conv, tz) + "\n\nShould I create these? (yes/no)",
        "steps": steps,
        "awaiting_input": True,
        "conversation_id": conv.id,
        "created_items": [],
        "done": False,
    }


def _confirm_text(conv: models.Conversation, tz: str) -> str:
    lines = ["Here's what I'll create:"]
    for d in conv.drafts:
        lines.append(f"• {intake.summarize_draft(d, tz)}")
    if any(d["type"] == "assignment" for d in conv.drafts):
        lines.append(
            "(Each assignment will also be broken into subtasks so it shows up in Tasks.)"
        )
    return "\n".join(lines)


def _do_create(db: Session, user_id: int, conv: models.Conversation, steps, tz) -> dict:
    created = create_drafts(db, user_id, conv.drafts)
    conv.status = "done"
    db.commit()
    n_assign = sum(1 for c in created if c["type"] == "assignment")
    n_exam = sum(1 for c in created if c["type"] == "exam")
    n_task = sum(1 for c in created if c["type"] == "task")
    subtasks = sum(c["subtask_count"] for c in created)
    steps.append(
        _step("intake", "create_items",
              f"Created {n_assign} assignment(s), {n_exam} exam(s), {n_task} task(s) "
              f"and {subtasks} subtask(s).")
    )
    summary = []
    if n_assign:
        summary.append(f"{n_assign} assignment(s) (with {subtasks} subtasks)")
    if n_exam:
        summary.append(f"{n_exam} exam(s)")
    if n_task:
        summary.append(f"{n_task} task(s)")
    reply = (
        "Done! I created " + ", ".join(summary) + ". "
        "They're now on your Assignments, Tasks and Exams pages. "
        "Want me to build a study schedule around them? Just say "
        "\"create a study plan\" and I'll propose one for your approval."
    )
    return {
        "reply": reply,
        "steps": steps,
        "awaiting_input": False,
        "conversation_id": conv.id,
        "created_items": created,
        "done": True,
    }
