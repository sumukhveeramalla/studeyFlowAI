"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "medium", "high"]
AssignmentStatus = Literal["not_started", "in_progress", "completed"]
TaskStatus = Literal["not_started", "in_progress", "completed"]
EventKind = Literal["class", "exam", "assignment", "study", "personal", "meeting"]


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Courses ----
class CourseBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: str = ""
    color: str = "#2563eb"
    instructor: str = ""


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    color: Optional[str] = None
    instructor: Optional[str] = None


class CourseOut(ORMBase, CourseBase):
    id: int


# ---- Assignments ----
class AssignmentBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    due_at: datetime
    priority: Priority = "medium"
    status: AssignmentStatus = "not_started"
    estimated_hours: float = Field(default=2.0, ge=0, le=200)
    course_id: Optional[int] = None


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: Optional[Priority] = None
    status: Optional[AssignmentStatus] = None
    estimated_hours: Optional[float] = Field(default=None, ge=0, le=200)
    course_id: Optional[int] = None


class AssignmentOut(ORMBase, AssignmentBase):
    id: int
    completed_at: Optional[datetime] = None
    course: Optional[CourseOut] = None


# ---- Tasks ----
class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: Priority = "medium"
    estimated_minutes: int = Field(default=60, ge=5, le=1440)
    deadline: Optional[datetime] = None
    status: TaskStatus = "not_started"
    order_index: int = 0
    assignment_id: Optional[int] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    priority: Optional[Priority] = None
    estimated_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    deadline: Optional[datetime] = None
    status: Optional[TaskStatus] = None
    order_index: Optional[int] = None
    assignment_id: Optional[int] = None


class TaskOut(ORMBase, TaskBase):
    id: int
    completed_at: Optional[datetime] = None


# ---- Exams ----
class ExamBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    start_at: datetime
    end_at: datetime
    topics: list[str] = Field(default_factory=list)
    prep_hours: float = Field(default=6.0, ge=0, le=200)
    priority: Priority = "high"
    prep_progress: float = Field(default=0.0, ge=0, le=1)
    course_id: Optional[int] = None


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    topics: Optional[list[str]] = None
    prep_hours: Optional[float] = Field(default=None, ge=0, le=200)
    priority: Optional[Priority] = None
    prep_progress: Optional[float] = Field(default=None, ge=0, le=1)
    course_id: Optional[int] = None


class ExamOut(ORMBase, ExamBase):
    id: int
    course: Optional[CourseOut] = None


# ---- Events ----
class EventBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: EventKind = "personal"
    start_at: datetime
    end_at: datetime
    is_fixed: bool = True
    color: Optional[str] = None
    location: str = ""
    task_id: Optional[int] = None
    assignment_id: Optional[int] = None
    exam_id: Optional[int] = None
    source: str = "manual"


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = None
    kind: Optional[EventKind] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    is_fixed: Optional[bool] = None
    color: Optional[str] = None
    location: Optional[str] = None


class EventOut(ORMBase, EventBase):
    id: int


# ---- Preferences ----
class PreferenceOut(ORMBase):
    study_start_hour: int
    study_end_hour: int
    session_length_min: int
    break_min: int
    available_days: str
    default_priority: Priority
    timezone: str


class PreferenceUpdate(BaseModel):
    study_start_hour: Optional[int] = Field(default=None, ge=0, le=23)
    study_end_hour: Optional[int] = Field(default=None, ge=1, le=24)
    session_length_min: Optional[int] = Field(default=None, ge=15, le=240)
    break_min: Optional[int] = Field(default=None, ge=0, le=120)
    available_days: Optional[str] = None
    default_priority: Optional[Priority] = None
    timezone: Optional[str] = None


# ---- Dashboard ----
class DashboardStats(BaseModel):
    upcoming_assignments: int
    upcoming_exams: int
    todays_tasks: int
    conflicts_resolved: int


class StudyProgress(BaseModel):
    label: str
    completed: int
    total: int
    percent: float


class DashboardOut(BaseModel):
    stats: DashboardStats
    week_events: list[EventOut]
    upcoming_deadlines: list[AssignmentOut]
    focus_tasks: list[TaskOut]
    progress: list[StudyProgress]


# ---- Scheduling / proposals ----
class ScheduleBlock(BaseModel):
    title: str
    kind: str = "study"
    start_at: datetime
    end_at: datetime
    task_id: Optional[int] = None
    assignment_id: Optional[int] = None
    exam_id: Optional[int] = None


class InfeasibleItem(BaseModel):
    label: str
    needed_minutes: int
    placed_minutes: int
    reason: str


class GenerateScheduleRequest(BaseModel):
    horizon_days: int = Field(default=7, ge=1, le=30)


class NewEventInput(BaseModel):
    title: str = "Unexpected event"
    kind: EventKind = "meeting"
    start_at: datetime
    end_at: datetime


class ReplanRequest(BaseModel):
    new_event: Optional[NewEventInput] = None
    horizon_days: int = Field(default=7, ge=1, le=30)


class ValidationError(BaseModel):
    code: str
    message: str


class ValidationResult(BaseModel):
    ok: bool
    errors: list[ValidationError] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    events: list[ScheduleBlock]


class ProposalChange(BaseModel):
    added: list[ScheduleBlock] = Field(default_factory=list)
    moved: list[dict] = Field(default_factory=list)
    removed: list[int] = Field(default_factory=list)


class ProposalOut(ORMBase):
    id: int
    status: str
    reason: str
    summary: dict
    changes: dict
    created_at: datetime
    decided_at: Optional[datetime] = None


# ---- Decomposition ----
class DecomposeRequest(BaseModel):
    pass


class DecomposeResult(BaseModel):
    assignment_id: int
    mode: Literal["llm", "demo"]
    tasks: list[TaskOut]


# ---- Agents / chat ----
class AgentStepOut(ORMBase):
    idx: int
    agent: str
    tool: str
    note: str
    validation: Optional[dict] = None


class AgentRunOut(ORMBase):
    id: int
    user_message: str
    intent: str
    status: str
    mode: str
    reply: str
    proposal_id: Optional[int] = None
    created_at: datetime
    steps: list[AgentStepOut] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: Optional[int] = None


class CreatedItem(BaseModel):
    type: Literal["assignment", "exam", "task"]
    id: int
    title: str
    subtask_count: int = 0


class ChatResponse(BaseModel):
    run: AgentRunOut
    reply: str
    mode: str
    intent: str
    proposal: Optional[ProposalOut] = None
    # Multi-turn intake conversation state
    conversation_id: Optional[int] = None
    awaiting_input: bool = False
    created_items: list[CreatedItem] = Field(default_factory=list)
