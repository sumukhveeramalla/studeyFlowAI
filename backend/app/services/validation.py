"""Independent deterministic validation of a proposed set of study blocks.

This never calls an LLM. It is the source of truth for scheduling correctness.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .scheduling import Interval, Prefs
from .timeutil import ensure_aware, local_tz


@dataclass
class VError:
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


@dataclass
class VResult:
    ok: bool
    errors: list[VError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": [e.to_dict() for e in self.errors]}


@dataclass
class Candidate:
    """A proposed study block to validate."""

    title: str
    start_at: datetime
    end_at: datetime
    deadline: datetime | None = None


def validate_blocks(
    candidates: list[Candidate],
    fixed: list[Interval],
    prefs: Prefs,
) -> VResult:
    errors: list[VError] = []
    tz = local_tz(prefs.timezone)

    norm = [
        Candidate(
            c.title,
            ensure_aware(c.start_at),
            ensure_aware(c.end_at),
            ensure_aware(c.deadline) if c.deadline else None,
        )
        for c in candidates
    ]

    # 1. start < end
    for c in norm:
        if c.end_at <= c.start_at:
            errors.append(
                VError("invalid_time", f"'{c.title}' ends before it starts.")
            )

    # 2. within study hours (local)
    for c in norm:
        ls = c.start_at.astimezone(tz)
        le = c.end_at.astimezone(tz)
        if ls.hour < prefs.study_start_hour or (
            le.hour > prefs.study_end_hour
            or (le.hour == prefs.study_end_hour and le.minute > 0)
        ):
            if prefs.study_end_hour < 24:
                errors.append(
                    VError(
                        "outside_hours",
                        f"'{c.title}' is outside study hours "
                        f"{prefs.study_start_hour}:00-{prefs.study_end_hour}:00.",
                    )
                )

    # 3. no overlap among study blocks
    ordered = sorted(norm, key=lambda c: c.start_at)
    for a, b in zip(ordered, ordered[1:]):
        if a.end_at > b.start_at:
            errors.append(
                VError(
                    "block_overlap",
                    f"'{a.title}' overlaps '{b.title}'.",
                )
            )

    # 4. no study block over a fixed commitment
    for c in norm:
        ci = Interval(c.start_at, c.end_at)
        for f in fixed:
            if ci.overlaps(f):
                errors.append(
                    VError(
                        "fixed_conflict",
                        f"'{c.title}' overlaps a fixed commitment.",
                    )
                )
                break

    # 5. deadline respected
    for c in norm:
        if c.deadline and c.end_at > c.deadline:
            errors.append(
                VError("deadline_violation", f"'{c.title}' ends after its deadline.")
            )

    return VResult(ok=len(errors) == 0, errors=errors)
