"""Deterministic greedy scheduling engine.

Produces study blocks around fixed commitments, honoring preferences and
deadlines. Never invents time slots; reports infeasibility explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from .timeutil import ensure_aware, local_tz

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Interval:
    start: datetime  # UTC aware
    end: datetime

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass
class WorkItem:
    label: str
    remaining_minutes: int
    priority: str
    deadline: datetime | None
    task_id: int | None = None
    assignment_id: int | None = None
    exam_id: int | None = None


@dataclass
class Block:
    title: str
    start_at: datetime
    end_at: datetime
    kind: str = "study"
    task_id: int | None = None
    assignment_id: int | None = None
    exam_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "kind": self.kind,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
            "task_id": self.task_id,
            "assignment_id": self.assignment_id,
            "exam_id": self.exam_id,
        }


@dataclass
class Infeasible:
    label: str
    needed_minutes: int
    placed_minutes: int
    reason: str

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "needed_minutes": self.needed_minutes,
            "placed_minutes": self.placed_minutes,
            "reason": self.reason,
        }


@dataclass
class Prefs:
    study_start_hour: int = 9
    study_end_hour: int = 21
    session_length_min: int = 90
    break_min: int = 15
    available_days: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)  # Mon=0
    timezone: str = "America/New_York"


@dataclass
class ScheduleResult:
    blocks: list[Block] = field(default_factory=list)
    infeasible: list[Infeasible] = field(default_factory=list)
    explanation: str = ""


def _free_slots_for_day(
    day_local: datetime, prefs: Prefs, busy: list[Interval]
) -> list[Interval]:
    """Compute free intervals (UTC) within a single local calendar day."""
    tz = local_tz(prefs.timezone)
    day_start_local = datetime.combine(
        day_local.date(), time(prefs.study_start_hour, 0), tzinfo=tz
    )
    end_hour = min(prefs.study_end_hour, 24)
    if end_hour >= 24:
        day_end_local = datetime.combine(
            day_local.date(), time(23, 59), tzinfo=tz
        ) + timedelta(minutes=1)
    else:
        day_end_local = datetime.combine(day_local.date(), time(end_hour, 0), tzinfo=tz)

    # convert local window to UTC
    from datetime import timezone as _tz

    win = Interval(
        day_start_local.astimezone(_tz.utc),
        day_end_local.astimezone(_tz.utc),
    )
    if win.end <= win.start:
        return []

    day_busy = sorted(
        (b for b in busy if b.overlaps(win)), key=lambda b: b.start
    )
    slots: list[Interval] = []
    cursor = win.start
    for b in day_busy:
        if b.start > cursor:
            slots.append(Interval(cursor, min(b.start, win.end)))
        cursor = max(cursor, b.end)
        if cursor >= win.end:
            break
    if cursor < win.end:
        slots.append(Interval(cursor, win.end))
    # drop zero/negative
    return [s for s in slots if s.end > s.start]


def compute_free_slots(
    start_local: datetime, horizon_days: int, prefs: Prefs, busy: list[Interval]
) -> list[Interval]:
    tz = local_tz(prefs.timezone)
    base = start_local.astimezone(tz)
    all_slots: list[Interval] = []
    for i in range(horizon_days):
        day = base + timedelta(days=i)
        if day.weekday() not in prefs.available_days:
            continue
        all_slots.extend(_free_slots_for_day(day, prefs, busy))
    all_slots.sort(key=lambda s: s.start)
    return all_slots


def schedule(
    now_utc: datetime,
    items: list[WorkItem],
    busy: list[Interval],
    prefs: Prefs,
    horizon_days: int = 7,
) -> ScheduleResult:
    """Greedily place work items into free slots before their deadlines."""
    tz = local_tz(prefs.timezone)
    start_local = now_utc.astimezone(tz)
    free = compute_free_slots(start_local, horizon_days, prefs, busy)

    # Only consider future slots (trim current partial slot to now).
    trimmed: list[Interval] = []
    for s in free:
        start = max(s.start, now_utc)
        if start < s.end:
            trimmed.append(Interval(start, s.end))
    free = trimmed

    # Sort demand: earliest deadline, then priority, then larger remaining.
    def key(it: WorkItem):
        dl = it.deadline or (now_utc + timedelta(days=horizon_days + 365))
        return (dl, PRIORITY_RANK.get(it.priority, 1), -it.remaining_minutes)

    items = sorted([WorkItem(**vars(i)) for i in items], key=key)

    blocks: list[Block] = []
    infeasible: list[Infeasible] = []
    # mutable copy of free slots as (start, end)
    slots = [Interval(s.start, s.end) for s in free]
    session = prefs.session_length_min
    brk = prefs.break_min

    for it in items:
        placed = 0
        need = it.remaining_minutes
        for slot in slots:
            if need <= 0:
                break
            if it.deadline and slot.start >= it.deadline:
                continue
            cursor = slot.start
            while need > 0 and cursor < slot.end:
                if it.deadline and cursor >= it.deadline:
                    break
                avail = int((slot.end - cursor).total_seconds() // 60)
                if avail < 15:  # too small to be useful
                    break
                chunk = min(session, need, avail)
                if it.deadline:
                    max_before_dl = int((it.deadline - cursor).total_seconds() // 60)
                    chunk = min(chunk, max_before_dl)
                if chunk < 15:
                    break
                b_end = cursor + timedelta(minutes=chunk)
                blocks.append(
                    Block(
                        title=f"Study: {it.label}",
                        start_at=cursor,
                        end_at=b_end,
                        task_id=it.task_id,
                        assignment_id=it.assignment_id,
                        exam_id=it.exam_id,
                    )
                )
                need -= chunk
                placed += chunk
                cursor = b_end + timedelta(minutes=brk)
            # shrink the slot so later items don't reuse it
            slot.start = cursor
        if need > 0:
            reason = (
                "No free time before the deadline."
                if it.deadline
                else "Not enough free time in the planning horizon."
            )
            infeasible.append(
                Infeasible(
                    label=it.label,
                    needed_minutes=it.remaining_minutes,
                    placed_minutes=placed,
                    reason=reason,
                )
            )

    blocks.sort(key=lambda b: b.start_at)
    if infeasible:
        parts = [
            f"{x.label}: scheduled {x.placed_minutes} of {x.needed_minutes} min ({x.reason})"
            for x in infeasible
        ]
        explanation = "Some work could not be fully scheduled. " + " | ".join(parts)
    else:
        explanation = f"Scheduled {len(blocks)} study block(s) with no conflicts."
    return ScheduleResult(blocks=blocks, infeasible=infeasible, explanation=explanation)


def intervals_from_events(events: list) -> list[Interval]:
    out = []
    for e in events:
        out.append(Interval(ensure_aware(e.start_at), ensure_aware(e.end_at)))
    return out
