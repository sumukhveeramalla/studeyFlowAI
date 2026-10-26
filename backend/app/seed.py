"""Idempotent sample data seeding. All dates are relative to now."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .config import get_settings
from .services.timeutil import local_tz

DEMO_USER_ID = 1


def _at(tz, base_date, hour, minute=0) -> datetime:
    """A local datetime on base_date at hour:minute, returned as UTC."""
    local = datetime.combine(base_date, time(hour, minute), tzinfo=tz)
    return local.astimezone(timezone.utc)


def ensure_profile(db: Session) -> models.User:
    """Always ensure the demo student profile + default preferences exist.

    This creates NO academic content — it's the minimum the single-user app needs
    to function. Safe to call on every startup.
    """
    settings = get_settings()
    user = db.get(models.User, DEMO_USER_ID)
    if user is None:
        user = models.User(
            id=DEMO_USER_ID,
            name="Student",
            email="",
            timezone=settings.default_timezone,
        )
        db.add(user)
        db.flush()
    pref = db.scalar(
        select(models.Preference).where(models.Preference.user_id == DEMO_USER_ID)
    )
    if pref is None:
        db.add(
            models.Preference(
                user_id=DEMO_USER_ID,
                study_start_hour=9,
                study_end_hour=21,
                session_length_min=90,
                break_min=15,
                available_days="0,1,2,3,4,5,6",
                default_priority="medium",
                timezone=settings.default_timezone,
            )
        )
    db.commit()
    return db.get(models.User, DEMO_USER_ID)


def seed(db: Session) -> None:
    """Startup hook. Ensures the profile exists and, when SEED_SAMPLE_DATA is on,
    populates sample academic data (only if the account has none yet)."""
    ensure_profile(db)
    settings = get_settings()
    if not settings.seed_sample_data:
        return
    has_content = db.scalar(
        select(models.Assignment).where(models.Assignment.user_id == DEMO_USER_ID)
    )
    if has_content:
        return
    seed_sample_data(db)


def seed_sample_data(db: Session) -> None:
    """Populate the demo student with realistic sample academic data."""
    settings = get_settings()
    tz = local_tz(settings.default_timezone)
    now = datetime.now(timezone.utc)
    today_local = now.astimezone(tz).date()

    # make the demo profile look like the original sample student
    user = db.get(models.User, DEMO_USER_ID)
    if user and user.name == "Student":
        user.name = "Alex Johnson"
        user.email = "alex@university.edu"
        db.flush()

    courses = {
        "ml": models.Course(user_id=DEMO_USER_ID, name="Machine Learning", code="CS 229", color="#2563eb", instructor="Dr. Ng"),
        "ds": models.Course(user_id=DEMO_USER_ID, name="Data Structures", code="CS 106B", color="#7c3aed", instructor="Dr. Roberts"),
        "chem": models.Course(user_id=DEMO_USER_ID, name="Chemistry", code="CHEM 101", color="#059669", instructor="Dr. Lee"),
        "math": models.Course(user_id=DEMO_USER_ID, name="Mathematics", code="MATH 51", color="#d97706", instructor="Dr. Patel"),
    }
    for c in courses.values():
        db.add(c)
    db.flush()

    def next_weekday(weekday: int, offset_weeks: int = 0):
        days_ahead = (weekday - today_local.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # always in the future
        return today_local + timedelta(days=days_ahead + 7 * offset_weeks)

    friday = next_weekday(4)  # Fri
    monday = next_weekday(0)  # next Mon
    wednesday = next_weekday(2)
    tomorrow = today_local + timedelta(days=1)

    assignments = [
        models.Assignment(
            user_id=DEMO_USER_ID, course_id=courses["ml"].id,
            title="Machine Learning Homework 3",
            description="Implement and evaluate a neural network model on the provided dataset.",
            due_at=_at(tz, friday, 23, 59), priority="high", status="in_progress",
            estimated_hours=6.0,
        ),
        models.Assignment(
            user_id=DEMO_USER_ID, course_id=courses["ds"].id,
            title="Data Structures Project: Graph Library",
            description="Build a reusable graph data structure with traversal algorithms.",
            due_at=_at(tz, wednesday, 23, 59), priority="medium", status="not_started",
            estimated_hours=5.0,
        ),
        models.Assignment(
            user_id=DEMO_USER_ID, course_id=courses["math"].id,
            title="Linear Algebra Problem Set 5",
            description="Problems on eigenvalues, eigenvectors and diagonalization.",
            due_at=_at(tz, monday, 17, 0), priority="medium", status="not_started",
            estimated_hours=3.0,
        ),
        models.Assignment(
            user_id=DEMO_USER_ID, course_id=courses["chem"].id,
            title="Lab Report: Titration",
            description="Write up the acid-base titration lab results.",
            due_at=_at(tz, today_local + timedelta(days=9), 23, 59),
            priority="low", status="not_started", estimated_hours=2.5,
        ),
    ]
    for a in assignments:
        db.add(a)
    db.flush()

    ml_assignment = assignments[0]
    ml_tasks = [
        ("Review neural-network lecture notes", 60, 0),
        ("Implement the model", 120, 1),
        ("Run experiments", 90, 2),
        ("Analyze results", 60, 3),
        ("Write and submit the report", 30, 4),
    ]
    for title, minutes, idx in ml_tasks:
        db.add(
            models.Task(
                user_id=DEMO_USER_ID, assignment_id=ml_assignment.id, title=title,
                priority="high", estimated_minutes=minutes,
                deadline=ml_assignment.due_at, status="not_started", order_index=idx,
            )
        )

    # a couple of standalone tasks
    db.add(
        models.Task(
            user_id=DEMO_USER_ID, title="Email professor about extension request",
            priority="low", estimated_minutes=15,
            deadline=_at(tz, tomorrow, 18, 0), status="not_started",
        )
    )

    exams = [
        models.Exam(
            user_id=DEMO_USER_ID, course_id=courses["chem"].id, title="Chemistry Midterm",
            start_at=_at(tz, monday, 10, 0), end_at=_at(tz, monday, 12, 0),
            topics=["Stoichiometry", "Acid-base reactions", "Thermochemistry"],
            prep_hours=6.0, priority="high", prep_progress=0.2,
        ),
        models.Exam(
            user_id=DEMO_USER_ID, course_id=courses["math"].id, title="Linear Algebra Quiz",
            start_at=_at(tz, wednesday, 9, 0), end_at=_at(tz, wednesday, 10, 0),
            topics=["Matrix operations", "Determinants"],
            prep_hours=3.0, priority="medium", prep_progress=0.0,
        ),
    ]
    for e in exams:
        db.add(e)
    db.flush()

    # Fixed recurring-ish classes for the next 10 days + a study session + personal.
    for day_offset in range(0, 11):
        d = today_local + timedelta(days=day_offset)
        wd = d.weekday()
        if wd in (0, 2, 4):  # Mon/Wed/Fri ML class 1-3pm (the fixed class)
            db.add(models.Event(
                user_id=DEMO_USER_ID, title="Machine Learning Lecture", kind="class",
                start_at=_at(tz, d, 13, 0), end_at=_at(tz, d, 15, 0),
                is_fixed=True, color="#2563eb", location="Gates B01", source="seed",
            ))
        if wd in (1, 3):  # Tue/Thu Chemistry lab
            db.add(models.Event(
                user_id=DEMO_USER_ID, title="Chemistry Lab", kind="class",
                start_at=_at(tz, d, 10, 0), end_at=_at(tz, d, 12, 0),
                is_fixed=True, color="#059669", location="Chem Hall 2", source="seed",
            ))

    # A seeded study session tomorrow 9-11am (the one the demo will conflict with).
    db.add(models.Event(
        user_id=DEMO_USER_ID, title="Study: Machine Learning Homework 3", kind="study",
        start_at=_at(tz, tomorrow, 9, 0), end_at=_at(tz, tomorrow, 11, 0),
        is_fixed=False, color="#2563eb", source="schedule",
        assignment_id=ml_assignment.id,
    ))

    # A study block today so the current week always has content to show.
    db.add(models.Event(
        user_id=DEMO_USER_ID, title="Study: Data Structures Project", kind="study",
        start_at=_at(tz, today_local, 16, 0), end_at=_at(tz, today_local, 17, 30),
        is_fixed=False, color="#7c3aed", source="schedule",
        assignment_id=assignments[1].id,
    ))
    db.add(models.Event(
        user_id=DEMO_USER_ID, title="Study: Chemistry Midterm prep", kind="study",
        start_at=_at(tz, today_local, 19, 0), end_at=_at(tz, today_local, 20, 30),
        is_fixed=False, color="#059669", source="schedule",
        exam_id=exams[0].id,
    ))

    # Personal commitments (one today, one in two days)
    db.add(models.Event(
        user_id=DEMO_USER_ID, title="Gym", kind="personal",
        start_at=_at(tz, today_local, 12, 0), end_at=_at(tz, today_local, 13, 0),
        is_fixed=True, color="#64748b", source="seed",
    ))
    db.add(models.Event(
        user_id=DEMO_USER_ID, title="Study group", kind="personal",
        start_at=_at(tz, today_local + timedelta(days=2), 18, 0),
        end_at=_at(tz, today_local + timedelta(days=2), 19, 0),
        is_fixed=True, color="#64748b", source="seed",
    ))

    db.commit()


def ensure_user(db: Session) -> models.User:
    user = db.get(models.User, DEMO_USER_ID)
    if not user:
        user = ensure_profile(db)
    return user
