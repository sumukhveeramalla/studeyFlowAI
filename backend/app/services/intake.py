"""Conversational intake: parse free-form text into assignments/exams/tasks,
ask for missing required fields across turns, confirm, then create.

Required fields (must be asked if missing):
  - assignment: title, due_at
  - exam:       title, start_at
  - task:       title, deadline

Other fields use sensible defaults with override. Creation happens immediately
after the user confirms. Each created assignment is auto-decomposed into subtasks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from .timeutil import local_tz
from .planner import get_prefs

ItemType = str  # "assignment" | "exam" | "task"

REQUIRED: dict[str, list[str]] = {
    "assignment": ["title", "due_at"],
    "exam": ["title", "start_at"],
    "task": ["title", "deadline"],
}

DATE_FIELD: dict[str, str] = {
    "assignment": "due_at",
    "exam": "start_at",
    "task": "deadline",
}

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}


@dataclass
class ParseResult:
    drafts: list[dict] = field(default_factory=list)
    note: str = ""


# ---------------------------------------------------------------------------
# Deterministic date parsing (demo mode + validation of LLM output)
# ---------------------------------------------------------------------------
def parse_date(text: str, tz_name: str, now: Optional[datetime] = None) -> Optional[str]:
    """Parse a natural-language date/time into an ISO UTC string, or None."""
    if not text:
        return None
    tz = local_tz(tz_name)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    t = text.strip().lower()

    # explicit ISO or YYYY-MM-DD
    try:
        dt = datetime.fromisoformat(text.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass

    # time-of-day within the text, e.g. "at 3pm", "10:30 am"
    hour, minute = 23, 59  # default deadline end-of-day
    tm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t)
    if tm:
        hour = int(tm.group(1)) % 12
        if tm.group(3) == "pm":
            hour += 12
        minute = int(tm.group(2) or 0)
    else:
        tm24 = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\b", t)
        if tm24:
            hour = int(tm24.group(1))
            minute = int(tm24.group(2) or 0)

    target_date = None

    if "day after tomorrow" in t:
        target_date = (now + timedelta(days=2)).date()
    elif "tomorrow" in t or "tmrw" in t or "tmr" in t:
        target_date = (now + timedelta(days=1)).date()
    elif "tonight" in t or "today" in t or "this evening" in t or "this afternoon" in t or "this morning" in t:
        target_date = now.date()
    else:
        # "next <weekday>" / "this <weekday>" / "<weekday>"
        mwd = re.search(r"\b(next|this)?\s*(" + "|".join(WEEKDAYS) + r")\b", t)
        if mwd:
            wd = WEEKDAYS[mwd.group(2)]
            ahead = (wd - now.weekday()) % 7
            if ahead == 0:
                ahead = 7  # upcoming, not today
            if mwd.group(1) == "next":
                ahead += 7 if ahead <= 7 else 0
            target_date = (now + timedelta(days=ahead)).date()
        else:
            # "in N days/weeks"
            mrel = re.search(r"\bin\s+(\d+)\s+(day|days|week|weeks)\b", t)
            if mrel:
                n = int(mrel.group(1))
                days = n * (7 if "week" in mrel.group(2) else 1)
                target_date = (now + timedelta(days=days)).date()
            else:
                # "Oct 30", "October 30", "30 Oct", "10/30"
                md = re.search(
                    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b",
                    t,
                )
                months = ["jan", "feb", "mar", "apr", "may", "jun",
                          "jul", "aug", "sep", "oct", "nov", "dec"]
                if md:
                    mon = months.index(md.group(1)[:3]) + 1
                    day = int(md.group(2))
                    year = now.year if (mon, day) >= (now.month, now.day) else now.year + 1
                    target_date = datetime(year, mon, day).date()
                else:
                    mslash = re.search(r"\b(\d{1,2})/(\d{1,2})\b", t)
                    if mslash:
                        mon = int(mslash.group(1))
                        day = int(mslash.group(2))
                        try:
                            year = now.year if (mon, day) >= (now.month, now.day) else now.year + 1
                            target_date = datetime(year, mon, day).date()
                        except ValueError:
                            target_date = None

    if target_date is None:
        return None
    local_dt = datetime.combine(target_date, time(hour % 24, minute), tzinfo=tz)
    return local_dt.astimezone(timezone.utc).isoformat()


def _guess_priority(text: str, default: str) -> str:
    t = text.lower()
    if any(w in t for w in ["urgent", "high priority", "important", "asap", "critical"]):
        return "high"
    if "low priority" in t:
        return "low"
    return default


def _guess_hours(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hour|hours|hr|hrs|h)\b", text.lower())
    if m:
        return float(m.group(1))
    return None


def _guess_type(text: str) -> ItemType:
    t = text.lower()
    if any(w in t for w in ["exam", "midterm", "final", "quiz", "test"]):
        return "exam"
    if any(w in t for w in ["assignment", "homework", "hw", "project", "essay",
                            "paper", "problem set", "pset", "lab report", "report"]):
        return "assignment"
    return "task"


# An "anchor" marks where an item starts inside prose. Each anchor becomes one
# draft; the text from one anchor to the next is that item's segment.
# Patterns are ordered; the first matching group label wins for that position.
_ANCHOR_RE = re.compile(
    r"\b("
    # exams
    r"midterm|final exam|final|exam|quiz|test"
    # assignments
    r"|assignment|homework|hw|problem set|pset|project|essay|paper|lab report|report|lab"
    # generic task noun
    r"|task|to-do|todo|chore|errand"
    # task verbs (reading/finishing/etc.)
    r"|read(?:ing)?|finish(?:ing)?|complete|submit|study(?: for)?|review|write(?:\s+up)?|prepare|do"
    r")\b",
    re.IGNORECASE,
)

# verbs that start a task clause (used to extract a task title verb phrase)
_TASK_VERBS = {"read", "reading", "finish", "finishing", "complete", "submit",
               "review", "write", "prepare", "do", "study"}


def _sentences(message: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", message.strip())
    return [p.strip() for p in parts if p.strip()]


_ITEM_NOUNS = {
    "midterm", "final", "exam", "quiz", "test", "assignment", "homework", "hw",
    "project", "essay", "paper", "report", "lab", "pset", "task", "to-do", "todo",
    "chore", "errand",
}


def _clauses(sentence: str) -> list[str]:
    """Split a sentence into clauses at separators that typically divide items."""
    parts = re.split(r"\s*(?:,|;|\band\b|\balso\b|\bthen\b|\bplus\b)\s*",
                     sentence, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _segment(message: str) -> list[str]:
    """Break the message into one text segment per detected item.

    Two passes:
    1. Split each sentence into clauses (comma / 'and' / 'also' / 'then').
    2. Within a clause there may still be two items (e.g. "a Machine Learning
       assignment due Friday and a Chemistry midterm"); but since 'and' already
       splits clauses, a clause normally holds one item. We merge an item-less
       continuation clause (attributes only: hours/priority/topics/date) back into
       the previous item so a single item's details stay together.
    """
    segments: list[str] = []
    for sentence in _sentences(message):
        for clause in _clauses(sentence):
            anchors = list(_ANCHOR_RE.finditer(clause))
            has_item = bool(anchors) or _clause_is_item(clause)
            if has_item:
                # keep the clause as-is, but trim a leading noun phrase start
                seg = clause.strip(" ,.;")
                if len(seg) >= 3:
                    segments.append(seg)
            else:
                # attribute-only continuation -> attach to previous item
                if segments:
                    segments[-1] = segments[-1] + ", " + clause.strip(" ,.;")
                elif len(clause.strip()) >= 3:
                    segments.append(clause.strip(" ,.;"))
    return segments


def _clause_is_item(clause: str) -> bool:
    low = clause.lower()
    if any(n in low.split() for n in _ITEM_NOUNS):
        return True
    first = low.split()[0] if low.split() else ""
    return first in _TASK_VERBS


def _segment_type(segment: str) -> ItemType:
    low = segment.lower()
    if any(w in low for w in ["exam", "midterm", "final", "quiz", "test"]):
        return "exam"
    if any(w in low for w in ["assignment", "homework", "hw", "project", "essay",
                              "paper", "problem set", "pset", "lab report", "report", "lab"]):
        return "assignment"
    # starts with a task verb → task
    first = low.split()[0] if low.split() else ""
    if first in _TASK_VERBS:
        return "task"
    return "task"


_LEADING_FILLER_RE = re.compile(
    r"^(?:"
    r"i\s+have\s+|i'?ve\s+got\s+|i\s+got\s+|i\s+need\s+to\s+|i\s+also\s+|"
    r"also\s+need\s+to\s+|also\s+have\s+|need\s+to\s+|have\s+to\s+|have\s+|"
    r"add\s+|create\s+|new\s+|there'?s\s+|there\s+is\s+|got\s+|"
    r"sign\s+up\s+for\s+|register\s+for\s+|enroll\s+in\s+|"
    r"quick\s+|a\s+|an\s+|the\s+|my\s+|some\s+|another\s+|"
    r"task\s+to\s+|task\s+|to-?do\s+to\s+|chore\s+to\s+|errand\s+to\s+"
    r")+",
    re.IGNORECASE,
)


def _title_from_segment(segment: str, itype: str) -> str:
    """Extract a human title from an item segment."""
    seg = segment.strip().strip(".")
    # strip leading filler ("I have a", "also need to", "add a", articles...)
    seg = _LEADING_FILLER_RE.sub("", seg).strip()
    # cut at the first date/attribute marker so dates/hours aren't in the title
    seg = re.split(
        r"\b(due|by|on|at|next|this|tomorrow|today|covering|worth|that\s|which\s|"
        r"will\s|around|about|approx|roughly|need|in\s+\d)\b",
        seg, maxsplit=1, flags=re.IGNORECASE,
    )[0]
    # for task verbs, keep the verb phrase (e.g. "read chapters 3 and 4")
    seg = seg.strip(" ,.;")
    if not seg:
        return segment.strip().strip(".").title()
    return seg.title()


def deterministic_parse(message: str, tz_name: str) -> ParseResult:
    """Parse a free-form paragraph into multiple item drafts (demo mode)."""
    drafts: list[dict] = []
    for seg in _segment(message):
        itype = _segment_type(seg)
        title = _title_from_segment(seg, itype)
        if not title or len(title) < 2:
            continue
        draft: dict = {
            "type": itype,
            "title": title,
            "priority": _guess_priority(seg, "medium"),
            "raw": seg,
        }
        date_iso = parse_date(seg, tz_name)
        if date_iso:
            draft[DATE_FIELD[itype]] = date_iso
        hours = _guess_hours(seg)
        if itype == "assignment":
            draft["estimated_hours"] = hours or 2.0
        elif itype == "exam":
            draft["prep_hours"] = hours or 6.0
            draft["topics"] = _extract_topics(seg)
        elif itype == "task":
            draft["estimated_minutes"] = int((hours or 1.0) * 60)
        drafts.append(draft)
    drafts = _dedupe(drafts)
    return ParseResult(drafts=drafts, note="deterministic")


def _extract_topics(segment: str) -> list[str]:
    m = re.search(r"covering\s+(.+?)(?:\.|,?\s+(?:need|due|by|on|worth|about)\b|$)",
                  segment, flags=re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1)
    topics = re.split(r"\s*(?:,|and|&)\s*", raw)
    return [t.strip().strip(".").title() for t in topics if t.strip()][:8]


def _dedupe(drafts: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for d in drafts:
        key = (d["type"], d["title"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def first_missing_field(draft: dict) -> Optional[str]:
    for f in REQUIRED.get(draft["type"], []):
        if not draft.get(f):
            return f
    return None


def question_for(draft: dict, missing: str) -> str:
    title = draft.get("title") or "this item"
    if missing == "title":
        return f"What should I call this {draft['type']}?"
    date_label = {
        "due_at": "due date",
        "start_at": "date and time",
        "deadline": "deadline",
    }[missing]
    kind = "exam" if draft["type"] == "exam" else draft["type"]
    return (
        f"When is the {date_label} for the {kind} \"{title}\"? "
        f"You can say things like \"next Friday\", \"tomorrow at 3pm\" or \"Oct 30\"."
    )


def summarize_draft(draft: dict, tz_name: str) -> str:
    tz = local_tz(tz_name)
    parts = [f"{draft['type']}: \"{draft.get('title')}\""]
    date_field = DATE_FIELD[draft["type"]]
    if draft.get(date_field):
        dt = datetime.fromisoformat(draft[date_field]).astimezone(tz)
        label = {"due_at": "due", "start_at": "on", "deadline": "by"}[date_field]
        parts.append(f"{label} {dt.strftime('%a %b %d, %I:%M %p')}")
    if draft.get("priority"):
        parts.append(f"{draft['priority']} priority")
    if draft["type"] == "assignment" and draft.get("estimated_hours"):
        parts.append(f"~{draft['estimated_hours']}h")
    if draft["type"] == "exam" and draft.get("prep_hours"):
        parts.append(f"~{draft['prep_hours']}h prep")
    return ", ".join(parts)


def apply_answer_to_draft(draft: dict, answer: str, tz_name: str) -> None:
    """Fill the pending field (or refine) from a user's follow-up answer."""
    missing = first_missing_field(draft)
    if missing in ("due_at", "start_at", "deadline"):
        date_iso = parse_date(answer, tz_name)
        if date_iso:
            draft[DATE_FIELD[draft["type"]]] = date_iso
            return
    if missing == "title" and answer.strip():
        draft["title"] = answer.strip().title()
        return
    # user may also supply extra details anytime
    date_iso = parse_date(answer, tz_name)
    if date_iso and not draft.get(DATE_FIELD[draft["type"]]):
        draft[DATE_FIELD[draft["type"]]] = date_iso
    hrs = _guess_hours(answer)
    if hrs:
        if draft["type"] == "assignment":
            draft["estimated_hours"] = hrs
        elif draft["type"] == "exam":
            draft["prep_hours"] = hrs
        elif draft["type"] == "task":
            draft["estimated_minutes"] = int(hrs * 60)


def is_affirmative(message: str) -> bool:
    return bool(
        re.search(r"\b(yes|yep|yeah|yup|sure|ok|okay|confirm|go ahead|do it|create|please)\b",
                  message.lower())
    )


def is_negative(message: str) -> bool:
    return bool(re.search(r"\b(no|nope|cancel|stop|don'?t|abort)\b", message.lower()))


# ---------------------------------------------------------------------------
# LLM-assisted parsing (used when an API key is configured)
# ---------------------------------------------------------------------------
def llm_parse(message: str, tz_name: str) -> Optional[ParseResult]:
    """Use the LLM to extract items; validate + normalize every field.

    Returns None if the LLM is unavailable or output is unusable, so the caller
    falls back to deterministic parsing (never presents a fallback as LLM output).
    """
    from ..agents.llm import structured_json

    now_iso = datetime.now(timezone.utc).isoformat()
    prompt = (
        "Extract academic items from the student's message. Each item is an "
        "assignment, exam, or task. Only include a date if the student stated one; "
        "otherwise omit it. Use natural-language dates exactly as written.\n"
        f"Current time (UTC): {now_iso}. Student timezone: {tz_name}.\n"
        f"Message: {message}"
    )
    schema = (
        '{"items": [{"type": "assignment|exam|task", "title": "string", '
        '"date_text": "the date phrase the user wrote, or empty", '
        '"priority": "low|medium|high", "estimated_hours": 2}]}'
    )
    data = structured_json(prompt, schema)
    if not data or not isinstance(data.get("items"), list) or not data["items"]:
        return None

    drafts: list[dict] = []
    for item in data["items"]:
        if not isinstance(item, dict):
            continue
        itype = item.get("type")
        if itype not in ("assignment", "exam", "task"):
            itype = _guess_type(str(item.get("title", "")))
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        draft: dict = {
            "type": itype,
            "title": title.title() if title.islower() else title,
            "priority": item.get("priority")
            if item.get("priority") in ("low", "medium", "high")
            else "medium",
            "raw": message,
        }
        date_text = item.get("date_text") or ""
        date_iso = parse_date(date_text, tz_name) if date_text else None
        if date_iso:
            draft[DATE_FIELD[itype]] = date_iso
        hrs = item.get("estimated_hours")
        try:
            hrs = float(hrs) if hrs is not None else None
        except (TypeError, ValueError):
            hrs = None
        if itype == "assignment":
            draft["estimated_hours"] = hrs or 2.0
        elif itype == "exam":
            draft["prep_hours"] = hrs or 6.0
            draft["topics"] = item.get("topics") if isinstance(item.get("topics"), list) else []
        elif itype == "task":
            draft["estimated_minutes"] = int((hrs or 1.0) * 60)
        drafts.append(draft)

    if not drafts:
        return None
    return ParseResult(drafts=drafts, note="llm")
