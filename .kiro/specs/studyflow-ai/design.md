# StudyFlow AI — Design

## 1. System Architecture

```
┌────────────────────────────────────────────────────────────┐
│  React + TS + Vite + Tailwind (frontend/)                    │
│  Pages: Dashboard, Calendar, Assignments, Exams, Tasks,      │
│         AI Assistant, Analytics, Settings                    │
│  State: TanStack Query over a typed API client (axios)       │
└───────────────┬──────────────────────────────────────────────┘
                │ REST (JSON, /api/*)
┌───────────────▼──────────────────────────────────────────────┐
│  FastAPI (backend/app)                                        │
│  Routers → Services → SQLAlchemy (SQLite)                     │
│  Scheduling engine (deterministic) + Validation layer         │
│  LangGraph agent workflow (supervisor + specialists + tools)  │
└──────────────────────────────────────────────────────────────┘
```

- Backend runs on `:8000`, frontend dev server on `:5173` and proxies `/api` → backend.
- Single demo student profile (id=1) seeded on first run; no auth for MVP.

## 2. Backend layout

```
backend/
  app/
    main.py            # FastAPI app, CORS, router registration, startup seed
    database.py        # engine, SessionLocal, Base, get_db
    models.py          # SQLAlchemy ORM models
    schemas.py         # Pydantic request/response models
    config.py          # settings from env (.env)
    seed.py            # idempotent sample data (dates relative to now)
    routers/
      courses.py assignments.py tasks.py exams.py events.py
      dashboard.py schedule.py chat.py agents.py preferences.py
    services/
      crud.py          # generic + entity CRUD helpers
      scheduling.py    # deterministic scheduling engine
      validation.py    # deterministic validators
      proposals.py     # build/apply/reject proposals (diff vs current)
      decomposition.py # deterministic task breakdown templates
      stats.py         # dashboard statistics
    agents/
      state.py         # AgentState TypedDict
      llm.py           # LLM factory + availability + structured output
      tools.py         # @tool functions wrapping services
      graph.py         # LangGraph StateGraph wiring
      nodes.py         # supervisor + specialist node fns
  tests/               # pytest
  requirements.txt
  .env.example
```

## 3. Database schema (SQLAlchemy / SQLite)

- **users**(id, name, email, timezone, created_at)
- **preferences**(id, user_id→users, study_start_hour, study_end_hour,
  session_length_min, break_min, available_days(csv), default_priority, timezone)
- **courses**(id, user_id, name, code, color, instructor)
- **assignments**(id, user_id, course_id→courses?, title, description, due_at(UTC),
  priority, status, estimated_hours, completed_at?)
- **tasks**(id, user_id, assignment_id→assignments?, title, priority,
  estimated_minutes, deadline(UTC)?, status, order_index, completed_at?)
- **exams**(id, user_id, course_id?, title, start_at(UTC), end_at(UTC),
  topics(json), prep_hours, priority, prep_progress)
- **events**(id, user_id, title, kind, start_at(UTC), end_at(UTC), is_fixed,
  color?, location?, task_id→tasks?, assignment_id?, exam_id?, source)
      kind ∈ {class, exam, assignment, study, personal, meeting}
      source ∈ {manual, schedule, seed}
- **proposals**(id, user_id, status(pending/approved/rejected), reason, summary(json),
  changes(json), created_at, decided_at?)
      changes = {added:[event], moved:[{id,from,to}], removed:[event_id]}
- **agent_runs**(id, user_id, user_message, intent, status, created_at)
- **agent_steps**(id, run_id→agent_runs, idx, agent, tool, note, validation(json), created_at)

Relationships use `ondelete=SET NULL` for soft references so deletes never orphan-crash.

## 4. API structure (prefix `/api`)

CRUD (list/create/get/update/delete) for: `courses`, `assignments`, `tasks`,
`exams`, `events`.

- `GET  /dashboard` — overview cards + week events + deadlines + focus tasks + progress.
- `GET  /preferences` / `PUT /preferences`.
- `POST /assignments/{id}/decompose` — generate + persist subtasks.
- `POST /schedule/generate` — build study blocks → returns a **proposal** (not applied).
- `POST /schedule/replan` — body: new/changed event → returns a **proposal**.
- `POST /schedule/validate` — validate an arbitrary set of events.
- `GET  /proposals` / `GET /proposals/{id}`.
- `POST /proposals/{id}/approve` / `POST /proposals/{id}/reject`.
- `POST /chat` — run the LangGraph workflow; returns assistant message, run id,
  agent steps, and an optional proposal.
- `GET  /agents/runs` / `GET /agents/runs/{id}` — activity history.

Errors: FastAPI `HTTPException` with `{detail}`; 404 missing, 422 validation,
409 invalid state (e.g. deciding an already-decided proposal).

## 5. Scheduling algorithm (deterministic greedy)

Inputs: pending tasks (+ exam prep pseudo-tasks), fixed events, preferences, horizon.

1. Build **demand**: one work item per unscheduled task with remaining minutes =
   `estimated_minutes`; exam prep → `prep_hours*60 * (1 - prep_progress)`.
   Items linked to assignments use the task estimate only (no double count).
2. Build **busy** set from all fixed events (+ already-accepted study blocks when
   replanning preserves them).
3. For each day in the horizon, within `[study_start_hour, study_end_hour]`,
   subtract busy intervals and break buffers → ordered list of **free slots**.
4. Sort demand by (deadline asc, priority desc, remaining desc). Greedily place
   each item into the earliest free slot(s) before its deadline, chunked to
   `session_length_min` with `break_min` between sessions. Split across days.
5. Emit study-block events. If an item cannot be fully placed before its deadline,
   record an **infeasibility** entry (needed vs placed minutes). Never invent slots.
6. Return `{blocks, infeasible[], explanation}`.

**Replanning**: inject the new fixed event into busy; find study blocks that now
overlap it (affected). Remove affected blocks, keep the rest, re-run step 4 only
for the freed demand, preferring to preserve untouched blocks (minimal change).

## 6. Validation layer (independent, deterministic)

`validate(events, fixed, prefs) -> ValidationResult{ok, errors[]}` checks:
- no overlap among study blocks; no study block overlapping a fixed event;
- start < end and within study hours; deadlines respected for linked items;
- total scheduled ≤ available hours. Pure Python, no LLM.

## 7. LangGraph architecture

`AgentState` (TypedDict): `user_message, user_id, intent, context(dict),
proposal(dict?), validation(dict?), messages[], steps[], reply, retries`.

Nodes & edges:

```
START → supervisor ──(intent)──┐
   ├ decompose → academic? → task_planner → END
   ├ schedule  → scheduler → validate ─(ok)→ END
   │                              └(fail & retries<2)→ scheduler
   ├ replan    → replanner → validate ─(ok)→ END
   │                              └(fail & retries<2)→ replanner
   ├ query     → academic (read tools) → END
   └ clarify   → END (asks a question)
```

- **supervisor**: classifies intent (LLM when available, else keyword router) into
  {decompose, schedule, replan, query, clarify}; writes `intent` + extracted params.
- **academic**: reads courses/assignments/exams via tools; answers queries; flags
  missing info.
- **task_planner**: decomposition tool → validated subtasks (persisted).
- **scheduler**: scheduling tool → proposal in state.
- **replanner**: replan tool (adds the new event to context) → proposal in state.
- **validate**: runs the deterministic validator on the proposal; sets `validation`;
  conditional edge loops back on failure (max 2 retries) then annotates feasibility.

Every node appends an `agent_steps` record (agent, tool, note, validation) to the
run so the Agent Activity panel reflects real execution. Proposals are returned,
never auto-applied (human-in-the-loop).

### Tools (`@tool`, wrap services, deterministic)
`get_academic_context`, `decompose_assignment`, `generate_schedule`,
`replan_schedule`, `validate_schedule`, `list_events`, `get_preferences`.

## 8. LLM configuration & fallback

`config.py` reads `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_MODEL`. `llm.py`
exposes `llm_available()` and `get_llm()`. When unavailable, supervisor uses a
keyword/regex router and task_planner uses `decomposition.py` templates — all
labeled `mode="demo"` in responses so fallbacks are never presented as real LLM
reasoning. Malformed/slow LLM output falls back to deterministic paths.

## 9. Frontend component structure

```
frontend/src/
  main.tsx, App.tsx, index.css (Tailwind + Inter)
  lib/api.ts (axios client + typed calls), lib/types.ts, lib/format.ts
  components/
    layout/{Sidebar,Topbar,AppShell}
    ui/{Card,Button,Badge,Modal,Input,Select,Spinner,EmptyState,StatCard}
    calendar/WeekCalendar, calendar/EventPill
    agent/{ChatPanel,AgentActivity,ProposalPreview}
  pages/{Dashboard,Calendar,Assignments,Exams,Tasks,Assistant,Analytics,Settings}
  hooks/ (TanStack Query hooks per resource)
```

Design language: white / very-light-blue (`#f5f8ff`) background, primary blue
(`#2563eb`), rounded-2xl cards, subtle borders/shadows, Inter font, color-coded
priorities & event kinds, polished empty/loading states. React Router for routes.

## 10. Human approval workflow (UI)

Chat / assistant returns a proposal → `ProposalPreview` renders original vs
proposed, added/moved/removed with explanations and Approve/Reject buttons →
calls `/proposals/{id}/approve|reject` → invalidates queries so Dashboard &
Calendar refetch.

## 11. Error handling

Backend: typed exceptions → HTTP codes; LLM wrapped in try/except with fallback;
scheduling returns structured infeasibility instead of throwing. Frontend: query
error/empty/loading states; form validation with inline messages; toasts for
mutations.

## 12. Testing strategy

Pytest with a function-scoped in-memory/temp SQLite DB and FastAPI TestClient:
CRUD + persistence, decomposition schema validation, priority handling, overlap
detection, deadline math, scheduling feasibility + infeasibility, replan-after-
conflict, fixed-event preservation, approve/reject effects, API error codes, and a
**smoke test** running the full replanning demo (seed → replan → proposal →
validate → approve → verify persisted). Frontend: Vitest + Testing Library smoke
test for the API client and a key component.
