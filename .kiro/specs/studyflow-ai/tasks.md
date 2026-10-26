# StudyFlow AI — Implementation Tasks

Legend: [ ] todo · [x] done. Tasks are ordered by dependency.

## 1. Scaffolding & database
- [x] 1.1 Backend project (requirements.txt, .env.example, config, database engine).
- [x] 1.2 SQLAlchemy models + relationships (users, preferences, courses, assignments, tasks, exams, events, proposals, agent_runs, agent_steps).
- [x] 1.3 Pydantic schemas for all entities + requests/responses.
- [x] 1.4 Idempotent seed with dates relative to now (ML, Data Structures, Chemistry, Mathematics; assignments, exams, classes, tasks, personal events).

## 2. Services & REST endpoints
- [x] 2.1 CRUD service + routers for courses, assignments, tasks, exams, events.
- [x] 2.2 Dashboard stats service + endpoint.
- [x] 2.3 Preferences endpoints.
- [x] 2.4 FastAPI app wiring (CORS, routers, startup seed, OpenAPI).

## 3. Scheduling engine & validation
- [x] 3.1 Deterministic scheduling engine (free-slot computation, greedy placement, infeasibility report).
- [x] 3.2 Deterministic validation layer (overlaps, fixed-event conflicts, deadlines, hours).
- [x] 3.3 Proposals service (build diff, apply, reject) + endpoints.
- [x] 3.4 Deterministic decomposition templates + endpoint.

## 4. LangGraph agents & tools
- [x] 4.1 Agent state + LLM factory/availability.
- [x] 4.2 Tools wrapping services.
- [x] 4.3 Supervisor + specialist nodes (academic, task_planner, scheduler, replanner, validate) with conditional routing + recovery loop.
- [x] 4.4 Chat + agent-activity endpoints (persist runs/steps).

## 5. Frontend foundation
- [x] 5.1 Vite + React + TS + Tailwind + Inter; API client + types; AppShell (Sidebar, Topbar); routing; UI primitives.
- [x] 5.2 Dashboard page (cards, week calendar, bottom cards, embedded assistant).
- [x] 5.3 Assignments page (table, CRUD modals, search/filter/sort, decompose, schedule, analytics).
- [x] 5.4 Tasks page (CRUD, filters, parent assignment, progress).
- [x] 5.5 Calendar page (week/day/month, CRUD, conflicts, colors).

## 6. Agent UI & replanning
- [x] 6.1 ChatPanel + AgentActivity + ProposalPreview components.
- [x] 6.2 AI Assistant full page; approve/reject wired; query invalidation.

## 7. Remaining pages
- [x] 7.1 Exams page (CRUD + prep-plan request).
- [x] 7.2 Analytics page (Recharts: completion, workload, priority distribution).
- [x] 7.3 Settings page (preferences form).

## 8. Tests & verification
- [x] 8.1 Pytest suite (CRUD/persistence, decomposition, priority, overlap, deadlines, feasibility, replan, fixed-event preservation, approve/reject, API errors) + replanning smoke test.
- [x] 8.2 Frontend build + a Vitest smoke test.
- [x] 8.3 README (overview, features, architecture, setup, env, run, test, agent workflow, demo, limitations).
- [x] 8.4 Run backend tests + frontend build; verify end-to-end demo; report results.
