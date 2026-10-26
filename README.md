# StudyFlow AI

**Plan Smarter. Study Better.**

StudyFlow AI is an intelligent multi-agent academic assistant that helps college
students manage assignments, exams, study schedules, deadlines and other
commitments. Its differentiator is **adaptive agentic planning** — a
LangGraph-orchestrated multi-agent workflow that decomposes assignments, generates
conflict-free schedules, validates them deterministically, and performs
**human-approved dynamic replanning** when circumstances change.

This is a working end-to-end application (persistent data, real APIs, a
deterministic scheduling engine and a genuine agent graph), not a static mockup.

---

## Features

- **Dashboard** — live overview cards, Monday–Sunday weekly calendar with week
  navigation and clickable events, upcoming deadlines, today's focus tasks,
  study-progress bars, and an embedded AI assistant panel.
- **Assignments** — full CRUD, search, filter (course/status/priority), sort by
  deadline, mark complete, AI task decomposition, schedule generation, and
  analytics (completion, weekly workload, priority distribution).
- **Tasks** — CRUD, Today / This Week / Overdue / Completed filters, parent-assignment
  links, progress tracking and AI recommendations.
- **Calendar** — week / day / month views, event CRUD, fixed vs movable study
  blocks (dashed), color-coded kinds, conflict highlighting, and schedule generation.
- **Exams** — CRUD with topics, prep hours, priority, progress, and a prep-plan builder.
- **AI Assistant** — full-page chat backed by the agent graph, a live **Agent
  Activity** panel, run history, and a structured **proposal preview** with
  Approve / Reject.
- **Conversational intake** — describe your workload in plain language (e.g. "I have
  an ML assignment due Friday and a Chemistry midterm Monday"); the assistant extracts
  assignments/exams/tasks, **asks follow-up questions for any missing deadline**
  across turns, confirms, then creates everything. Each created assignment is
  **auto-decomposed into subtasks** so it also appears in Tasks, and the new items
  immediately feed scheduling, Assignments, Tasks, Exams and the Dashboard.
- **Analytics** — Recharts visualizations of workload, status and priority.
- **Settings** — study preferences (hours, session length, breaks, available days,
  timezone) applied by the scheduler, plus course management.

## Architecture

```
React + TS + Vite + Tailwind (frontend/)        FastAPI + SQLAlchemy + SQLite (backend/)
  TanStack Query → typed axios client  ──REST──▶  Routers → Services → ORM
  Pages, UI primitives, WeekCalendar               Deterministic scheduling engine
  Agent chat / activity / proposal UI              Independent validation layer
                                                   LangGraph multi-agent workflow
```

- **Scheduling engine** (`services/scheduling.py`): deterministic greedy placement of
  study blocks into free slots around fixed commitments, honoring preferences and
  deadlines, with explicit infeasibility reports (no invented slots).
- **Validation layer** (`services/validation.py`): independent, LLM-free checks for
  overlaps, fixed-event conflicts, study-hour bounds and deadline violations.
- **Agents** (`agents/`): a LangGraph `StateGraph` — Supervisor routes intent to
  Academic, Task-Planner, Scheduler or Replanner specialists; a Validator node runs
  the deterministic checks and loops back on failure (bounded retries); a Finalize
  node creates a **pending proposal** so nothing changes without human approval.

```
START → supervisor ─(intent)─┬ decompose → task_planner → END
                             ├ schedule  → scheduler → validate ─(ok)→ finalize → END
                             │                              └(fail<2)→ scheduler
                             ├ replan    → replanner → validate ─(ok)→ finalize → END
                             │                              └(fail<2)→ replanner
                             ├ query     → academic → END
                             └ clarify   → clarify → END
```

### Database models
`users`, `preferences`, `courses`, `assignments`, `tasks`, `exams`, `events`
(classes/exams/assignments/study/personal/meeting; fixed vs movable), `proposals`
(pending schedule diffs), `agent_runs` and `agent_steps` (observability). All
timestamps are stored in UTC; the client renders in the student's timezone.

## Requirements

- **Python 3.12** (3.11–3.12 recommended; LangGraph/pydantic wheels). `uv` optional.
- **Node 18+** (built with Node 23).

## Setup

### Backend

```bash
cd backend
# with uv (used during development):
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
# or with plain venv/pip:
# python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

cp .env.example .env        # optional; works without an API key (demo mode)
```

### Frontend

```bash
cd frontend
npm install
```

## Environment variables (`backend/.env`)

| Variable              | Default                      | Purpose                                            |
| --------------------- | ---------------------------- | -------------------------------------------------- |
| `OPENAI_API_KEY`      | *(empty)*                    | If set, agents use a real OpenAI-compatible model. Empty ⇒ deterministic **demo mode**. |
| `OPENAI_BASE_URL`     | `https://api.openai.com/v1`  | OpenAI-compatible endpoint.                        |
| `LLM_MODEL`           | `gpt-4o-mini`                | Chat model name.                                   |
| `LLM_TIMEOUT_SECONDS` | `30`                         | LLM call timeout.                                  |
| `DATABASE_URL`        | `sqlite:///./studyflow.db`   | Database URL.                                      |
| `CORS_ORIGINS`        | `http://localhost:5173,...`  | Allowed frontend origins.                          |
| `DEFAULT_TIMEZONE`    | `America/New_York`           | Seeded demo student timezone.                      |

Secrets are never committed (`.env` is gitignored; only `.env.example` is tracked).

## Running locally

Terminal 1 — backend (seeds sample data on first boot, serves OpenAPI at
`http://127.0.0.1:8000/docs`):

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Terminal 2 — frontend (proxies `/api` → backend):

```bash
cd frontend
npm run dev     # http://localhost:5173
```

## Testing

```bash
# Backend (pytest): CRUD/persistence, decomposition, overlap/deadline,
# feasibility, replan-after-conflict, fixed-event preservation, approve/reject,
# API errors, and a full replanning smoke test.
cd backend && .venv/bin/python -m pytest -q

# Frontend (Vitest) + production build type-check:
cd frontend && npm run test && npm run build
```

## Agent workflow explanation

1. **Supervisor** classifies the message intent (LLM when configured, otherwise a
   deterministic keyword router): `create`, `decompose`, `schedule`, `replan`,
   `query` or `clarify`.
2. **Intake (`create`)** — a stateful, multi-turn flow (not the single-pass graph).
   It parses the message into assignment/exam/task drafts, asks follow-up questions
   for missing **required** fields (title + deadline/date) one turn at a time,
   summarizes for **confirmation**, and only on "yes" creates the items — immediately,
   with assignments auto-decomposed into subtasks. Conversation state is persisted in
   a `conversations` row and the frontend passes `conversation_id` back each turn.
   Item creation is immediate (an explicit, low-risk request); only **schedule**
   changes stay approval-gated.
3. Other intents run the **LangGraph** specialists over real DB tools:
   - *Academic* reads assignments/exams/tasks and answers queries.
   - *Task-Planner* decomposes an assignment into validated subtasks (LLM or template).
   - *Scheduler* / *Replanner* call the deterministic scheduling engine.
4. **Validator** runs independent deterministic checks; on failure the graph loops
   back (max 2 retries) with the conflict info, then finalizes with a feasibility note.
5. **Finalize** writes a *pending* proposal and the workflow pauses — the schedule is
   **never modified without approval**. Approve/Reject applies or discards it.

Every node records an `agent_steps` row (agent, tool, note, validation), surfaced in
the **Agent Activity** panel and run history — no fabricated executions.

## Sample demo (core: dynamic replanning)

The seed creates a fictional student (Alex Johnson) with Machine Learning, Data
Structures, Chemistry and Mathematics courses; several assignments and exams; fixed
classes; study blocks; and personal events — **all dated relative to today**.

1. Start backend + frontend; open the **Dashboard**.
2. **Assignments** → pick one → click the **wand** to generate subtasks (or ask the
   assistant “Break down my Machine Learning assignment”).
3. Ask the assistant: **“Create a study plan for this week.”** Review the proposal,
   click **Approve** — new study blocks appear on the calendar.
4. Ask: **“I have an unexpected meeting tomorrow from 9 AM to 11 AM. Rearrange my
   study schedule without missing deadlines.”**
5. Inspect the **Agent Activity** (supervisor → replanner → validator → await
   approval) and the **proposal preview** (original vs proposed, added/removed blocks,
   explanations).
6. Click **Approve** → the meeting is saved, conflicting study blocks are rescheduled,
   and the Dashboard/Calendar update. Refresh — the changes persist.

## Known limitations

- **Single demo profile** (no authentication) — per the MVP scope.
- **LLM optional**: with no API key the app runs a clearly-labeled deterministic
  **demo mode**; fallback replies are never presented as model reasoning.
- The scheduler is a documented **greedy** MVP (earliest-deadline, then priority); it
  is deterministic and conflict-free but not globally optimal.
- Timezone handling targets a single student timezone (stored UTC, rendered local);
  multi-user tz negotiation is out of scope.
- **Canvas / Google Calendar / notifications** are intentionally **not** implemented
  (listed as stretch goals) and are not claimed to work.
- The production JS bundle is a single chunk (>500 kB); code-splitting is a future
  optimization.
```
