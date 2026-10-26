"""LangGraph node functions.

Nodes operate on AgentState. A DB session and user_id are injected via a module
level context set by the graph runner (per-request), keeping node signatures
compatible with LangGraph while still touching real services.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..services import planner, proposals
from ..services.scheduling import Interval
from ..services.timeutil import ensure_aware, local_tz
from . import tools
from .llm import llm_available, structured_json
from .planner_agent import plan_tasks
from .state import AgentState

MAX_RETRIES = 2


class RunContext:
    """Per-request context shared with nodes."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id


_ctx: RunContext | None = None


def set_context(ctx: RunContext) -> None:
    global _ctx
    _ctx = ctx


def _db() -> Session:
    assert _ctx is not None
    return _ctx.db


def _append_step(state: AgentState, agent: str, tool: str, note: str, validation=None):
    steps = state.get("steps", [])
    steps.append(
        {
            "idx": len(steps),
            "agent": agent,
            "tool": tool,
            "note": note,
            "validation": validation,
        }
    )
    state["steps"] = steps


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------
_TIME_RE = re.compile(
    r"(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm)?\s*(?:to|-|–|until)\s*(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm)?",
    re.IGNORECASE,
)


def _keyword_intent(msg: str) -> tuple[str, dict]:
    m = msg.lower()
    params: dict = {}

    # Replan: an explicit change to an EXISTING schedule (unexpected event, missed
    # session). Keep this first since it is a distinct, strong signal.
    if any(k in m for k in [
        "unexpected", "reschedule", "re-schedule", "replan", "re-plan", "missed",
        "can't make", "cannot make", "move my", "rearrange", "came up",
    ]):
        return "replan", params

    if any(k in m for k in ["break down", "breakdown", "decompose", "subtask", "sub-task", "split"]):
        return "decompose", params

    describes_items = _describes_new_items(m)

    # A PURE scheduling request names no new items — just asks to build/plan.
    # If the message also describes concrete new work, creating comes first.
    if not describes_items and any(k in m for k in [
        "study plan", "plan my", "study schedule", "allocate", "study time",
        "plan my week", "build a schedule", "build a study", "generate a schedule",
        "make a schedule", "make a study plan", "create a study plan",
        "create a schedule", "schedule my", "plan my day",
    ]):
        return "schedule", params

    # Creation / intake: the student is describing new work (deadlines, items to
    # submit/prepare/write). Create it first; they can schedule afterwards.
    if describes_items:
        return "create", params

    if any(k in m for k in ["prioritize", "priorit", "upcoming", "what do i", "show me", "list"]):
        return "query", params
    return "query", params


# Signals that the message describes new academic work to create.
_CREATE_NOUNS = [
    "assignment", "homework", "hw", "project", "essay", "paper", "report", "lab",
    "problem set", "pset", "exam", "midterm", "final", "quiz", "test", "presentation",
    "deadline", "letter", "response letter", "submission",
]
_CREATE_VERBS = [
    "submit", "prepare", "prepare for", "write", "finish", "complete", "read",
    "study for", "review", "work on", "turn in", "hand in", "need to", "have to",
]
_CREATE_PHRASES = [
    "add an assignment", "add a ", "add an ", "create an assignment", "new assignment",
    "new exam", "new task", "i have an", "i have a ", "i've got", "i got ",
    "sign up", "register", "enroll",
    "due ", "by november", "by december", "by monday", "by tuesday", "by wednesday",
    "by thursday", "by friday", "by saturday", "by sunday", "before 11", "tonight",
    "these are my tasks", "my tasks",
]


def _describes_new_items(m: str) -> bool:
    """Heuristic: does the message describe concrete new items (not just ask to plan)?"""
    if any(p in m for p in _CREATE_PHRASES):
        return True
    has_noun = any(re.search(r"\b" + re.escape(n) + r"\b", m) for n in _CREATE_NOUNS)
    has_verb = any(v in m for v in _CREATE_VERBS)
    # a due date/time pattern strongly implies a creatable item
    has_due = bool(
        re.search(r"\b(due|submit|before|by)\b.*\b(\d|today|tonight|tomorrow|mon|tue|wed|thu|fri|sat|sun|nov|dec|jan|oct)", m)
    )
    return (has_noun and (has_verb or has_due)) or has_due and has_verb


def _llm_intent(msg: str) -> tuple[str, dict] | None:
    data = structured_json(
        "Classify a student's request into exactly one intent.\n"
        "Intents:\n"
        "- create: the message describes NEW assignments, exams, or tasks to add "
        "(anything with a title + a deadline/date, or things to submit/prepare/"
        "write/finish). Choose 'create' even if the student also says 'plan my "
        "schedule' — creating the items comes first.\n"
        "- schedule: a pure request to build a study schedule with NO new items "
        "described (e.g. 'plan my week', 'create a study plan').\n"
        "- replan: change an existing schedule due to an unexpected event or a "
        "missed session.\n"
        "- decompose: break an existing assignment into subtasks.\n"
        "- query: ask about existing items (deadlines, priorities, lists).\n"
        "- clarify: the message is too vague to act on.\n"
        f"Message: {msg}",
        '{"intent": "create", "params": {}}',
    )
    if not data:
        return None
    intent = data.get("intent")
    if intent not in {"create", "decompose", "schedule", "replan", "query", "clarify"}:
        return None
    return intent, data.get("params") or {}


_UNAMBIGUOUS_SCHEDULE = [
    "study plan", "study schedule", "plan my week", "plan my day", "plan my schedule",
    "build a schedule", "build a study", "generate a schedule", "make a schedule",
    "make a study plan", "create a study plan", "create a schedule", "schedule my",
]


def supervisor(state: AgentState) -> AgentState:
    msg = state["user_message"]
    mode = "llm" if llm_available() else "demo"
    state["mode"] = mode
    intent, params = _keyword_intent(msg)
    # The LLM may refine intent, BUT don't let it override clear command phrases
    # (e.g. "create a study plan" is scheduling, not item creation).
    low = msg.lower()
    locked = (
        (intent == "schedule" and any(p in low for p in _UNAMBIGUOUS_SCHEDULE))
        or (intent == "replan" and any(
            p in low for p in ["unexpected", "reschedule", "replan", "rearrange", "missed"]
        ))
    )
    if mode == "llm" and not locked:
        llm_result = _llm_intent(msg)
        if llm_result:
            intent, params = llm_result
    state["intent"] = intent
    state["params"] = params
    state.setdefault("retries", 0)
    _append_step(
        state, "supervisor",
        "classify_intent",
        f"Routed request to '{intent}' (mode={mode}).",
    )
    return state


# ---------------------------------------------------------------------------
# Specialist nodes
# ---------------------------------------------------------------------------
def academic(state: AgentState) -> AgentState:
    db, uid = _db(), _ctx.user_id
    ctx = tools.get_academic_context(db, uid)
    state["context"] = ctx
    _append_step(state, "academic", "get_academic_context",
                 f"Loaded {len(ctx['assignments'])} assignments, "
                 f"{len(ctx['exams'])} exams, {len(ctx['open_tasks'])} open tasks.")

    # Build a grounded reply.
    now = datetime.now(timezone.utc)
    upcoming = [a for a in ctx["assignments"] if a["status"] != "completed"]
    lines = []
    if upcoming:
        lines.append("Here's what's coming up, ordered by priority and deadline:")
        ranked = sorted(
            upcoming,
            key=lambda a: (
                datetime.fromisoformat(a["due_at"]),
                {"high": 0, "medium": 1, "low": 2}.get(a["priority"], 1),
            ),
        )
        for a in ranked[:5]:
            due = datetime.fromisoformat(a["due_at"]).astimezone(timezone.utc)
            days = (due - now).days
            when = "overdue" if days < 0 else (f"due in {days} day(s)" if days else "due today")
            lines.append(f"• {a['title']} — {a['priority']} priority, {when}.")
    else:
        lines.append("You have no open assignments right now. Nice work!")
    if ctx["exams"]:
        nxt = ctx["exams"][0]
        lines.append(
            f"Next exam: {nxt['title']} with {int(nxt['prep_hours']*(1-nxt['prep_progress']))}h of prep left."
        )
    state["reply"] = "\n".join(lines)
    return state


def task_planner(state: AgentState) -> AgentState:
    db, uid = _db(), _ctx.user_id
    ctx = tools.get_academic_context(db, uid)
    assignments = ctx["assignments"]
    target = None
    msg = state["user_message"].lower()
    for a in assignments:
        if a["title"].lower() in msg or any(w in msg for w in a["title"].lower().split() if len(w) > 4):
            target = a
            break
    if target is None and assignments:
        target = sorted(
            [a for a in assignments if a["status"] != "completed"],
            key=lambda a: datetime.fromisoformat(a["due_at"]),
        )[0] if any(a["status"] != "completed" for a in assignments) else assignments[0]

    if not target:
        state["reply"] = "I couldn't find an assignment to break down. Add one first."
        _append_step(state, "task_planner", "decompose_assignment", "No assignment found.")
        return state

    from .. import models
    a = db.get(models.Assignment, target["id"])
    subtasks, tmode = plan_tasks(a.title, a.description, a.estimated_hours, a.priority)
    created = []
    for st in subtasks:
        t = models.Task(
            user_id=uid, assignment_id=a.id, title=st["title"],
            priority=st.get("priority", a.priority),
            estimated_minutes=st["estimated_minutes"], deadline=a.due_at,
            status="not_started", order_index=st.get("order_index", len(created)),
        )
        db.add(t)
        created.append(t)
    if a.status == "not_started":
        a.status = "in_progress"
    db.commit()
    _append_step(state, "task_planner", "decompose_assignment",
                 f"Generated {len(created)} subtasks for '{a.title}' (mode={tmode}).")
    bullet = "\n".join(f"{i+1}. {st['title']} (~{st['estimated_minutes']} min)"
                       for i, st in enumerate(subtasks))
    state["reply"] = f"I broke '{a.title}' into {len(subtasks)} tasks:\n{bullet}"
    return state


def scheduler(state: AgentState) -> AgentState:
    db, uid = _db(), _ctx.user_id
    result = planner.generate_schedule(db, uid, horizon_days=7)
    _append_step(state, "scheduler", "generate_schedule",
                 f"Produced {len(result.blocks)} study block(s). {result.explanation}")
    state["context"] = {
        "blocks": [b.to_dict() for b in result.blocks],
        "infeasible": [i.to_dict() for i in result.infeasible],
        "removed": [b["id"] for b in proposals.current_schedule_snapshot(db, uid)],
        "preserved": [],
        "new_event": None,
        "explanation": result.explanation,
    }
    return state


def replanner(state: AgentState) -> AgentState:
    db, uid = _db(), _ctx.user_id
    new_event = _extract_new_event(state, uid)
    result, preserved, removed_ids = planner.replan_schedule(db, uid, new_event, 7)
    note = (
        f"Detected {len(removed_ids)} conflicting block(s); "
        f"rescheduled {len(result.blocks)} new block(s), preserved {len(preserved)}."
    )
    _append_step(state, "replanner", "replan_schedule", note)
    stored_new = None
    if new_event:
        stored_new = {
            "title": new_event["title"],
            "kind": new_event["kind"],
            "start_at": new_event["start_at"].isoformat(),
            "end_at": new_event["end_at"].isoformat(),
        }
    state["context"] = {
        "blocks": [b.to_dict() for b in result.blocks],
        "preserved": [b.to_dict() for b in preserved],
        "removed": removed_ids,
        "infeasible": [i.to_dict() for i in result.infeasible],
        "new_event": stored_new,
        "new_event_obj": new_event,
        "explanation": result.explanation,
    }
    return state


def validate(state: AgentState) -> AgentState:
    db, uid = _db(), _ctx.user_id
    from .. import schemas  # noqa
    from ..services.scheduling import Block

    ctx = state.get("context", {})
    blocks = [_block_from_dict(b) for b in ctx.get("blocks", [])]
    preserved = [_block_from_dict(b) for b in ctx.get("preserved", [])]
    extra = None
    ne = ctx.get("new_event_obj")
    if ne:
        extra = Interval(ensure_aware(ne["start_at"]), ensure_aware(ne["end_at"]))
    result = planner.validate_result(db, uid, blocks + preserved, extra_fixed=extra)
    state["validation"] = result.to_dict()
    _append_step(
        state, "validator", "validate_schedule",
        ("Validation passed." if result.ok else
         f"Validation failed with {len(result.errors)} issue(s)."),
        validation=result.to_dict(),
    )
    return state


def finalize(state: AgentState) -> AgentState:
    """Create a pending proposal from the current context (human-in-the-loop)."""
    db, uid = _db(), _ctx.user_id
    from ..services.scheduling import Block

    ctx = state.get("context", {})
    added = [_block_from_dict(b) for b in ctx.get("blocks", [])]
    removed = ctx.get("removed", [])
    infeasible = ctx.get("infeasible", [])
    new_event = ctx.get("new_event")
    reason = ctx.get("explanation", "Proposed schedule changes.")
    validation = state.get("validation") or {}
    if not validation.get("ok", True):
        reason += " Note: validation flagged issues; review carefully."

    proposal = proposals.create_proposal(
        db, uid, added=added, moved=[], removed=removed,
        reason=reason, infeasible=infeasible, new_event=new_event,
    )
    state["proposal"] = {
        "id": proposal.id,
        "status": proposal.status,
        "reason": proposal.reason,
        "summary": proposal.summary,
        "changes": proposal.changes,
    }
    added_n = len(added)
    removed_n = len(removed)
    reply = (
        f"I've prepared a schedule proposal: {added_n} new study block(s)"
        + (f", removing {removed_n} conflicting block(s)" if removed_n else "")
        + ". Review the preview and approve or reject — nothing changes until you approve."
    )
    if infeasible:
        reply += f" Heads up: {len(infeasible)} item(s) couldn't be fully scheduled."
    state["reply"] = reply
    _append_step(state, "supervisor", "await_approval",
                 "Proposal created; awaiting human approval.")
    return state


def clarify(state: AgentState) -> AgentState:
    state["reply"] = (
        "Could you give me a bit more detail? For example, tell me which "
        "assignment to break down, or when your unexpected event is."
    )
    _append_step(state, "supervisor", "clarify", "Asked the student for clarification.")
    return state


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------
def route_from_supervisor(state: AgentState) -> str:
    return state.get("intent", "query")


def route_after_validate(state: AgentState) -> str:
    validation = state.get("validation") or {}
    if validation.get("ok", True):
        return "finalize"
    retries = state.get("retries", 0)
    if retries < MAX_RETRIES:
        state["retries"] = retries + 1
        # route back to whichever planner produced the context
        return "replan" if state.get("intent") == "replan" else "schedule"
    return "finalize"  # finalize with a feasibility warning


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _block_from_dict(d: dict):
    from ..services.scheduling import Block

    return Block(
        title=d["title"],
        start_at=ensure_aware(datetime.fromisoformat(d["start_at"])),
        end_at=ensure_aware(datetime.fromisoformat(d["end_at"])),
        kind=d.get("kind", "study"),
        task_id=d.get("task_id"),
        assignment_id=d.get("assignment_id"),
        exam_id=d.get("exam_id"),
    )


def _extract_new_event(state: AgentState, uid: int) -> dict | None:
    """Parse a time range from the message, or use explicit params."""
    params = state.get("params", {})
    if params.get("new_event"):
        ne = params["new_event"]
        try:
            return {
                "title": ne.get("title", "Unexpected event"),
                "kind": ne.get("kind", "meeting"),
                "start_at": ensure_aware(datetime.fromisoformat(ne["start_at"])),
                "end_at": ensure_aware(datetime.fromisoformat(ne["end_at"])),
            }
        except Exception:
            pass

    msg = state["user_message"]
    m = _TIME_RE.search(msg)
    prefs = planner.get_prefs(_db(), uid)
    tz = local_tz(prefs.timezone)
    now_local = datetime.now(timezone.utc).astimezone(tz)

    # Determine the day: default tomorrow, else today if "today" mentioned.
    day = (now_local + timedelta(days=1)).date()
    low = msg.lower()
    if "today" in low:
        day = now_local.date()
    elif "tomorrow" in low:
        day = (now_local + timedelta(days=1)).date()

    if not m:
        return None

    def hour24(h, ap):
        h = int(h)
        if ap:
            ap = ap.lower()
            if ap == "pm" and h != 12:
                h += 12
            if ap == "am" and h == 12:
                h = 0
        return h

    sh = hour24(m.group(1), m.group(3) or m.group(6))
    sm = int(m.group(2) or 0)
    eh = hour24(m.group(4), m.group(6) or m.group(3))
    em = int(m.group(5) or 0)
    from datetime import time as _time

    start_local = datetime.combine(day, _time(sh % 24, sm), tzinfo=tz)
    end_local = datetime.combine(day, _time(eh % 24, em), tzinfo=tz)
    if end_local <= start_local:
        end_local = start_local + timedelta(hours=1)

    title = "Unexpected meeting" if "meeting" in low else "Unexpected event"
    return {
        "title": title,
        "kind": "meeting",
        "start_at": start_local.astimezone(timezone.utc),
        "end_at": end_local.astimezone(timezone.utc),
    }
