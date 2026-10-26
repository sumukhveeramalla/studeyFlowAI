"""StudyFlow AI FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import (
    agents,
    assignments,
    chat,
    courses,
    dashboard,
    events,
    exams,
    preferences,
    schedule,
    tasks,
)
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield


settings = get_settings()

app = FastAPI(
    title="StudyFlow AI API",
    description="Plan Smarter. Study Better. Multi-agent academic assistant backend.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    courses.router,
    assignments.router,
    tasks.router,
    exams.router,
    events.router,
    dashboard.router,
    preferences.router,
    schedule.router,
    schedule.proposal_router,
    chat.router,
    agents.router,
):
    app.include_router(r)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "llm_enabled": settings.llm_enabled}


@app.get("/api/profile", tags=["profile"])
def profile():
    from .database import SessionLocal
    from .seed import ensure_user

    db = SessionLocal()
    try:
        user = ensure_user(db)
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "timezone": user.timezone,
            "llm_enabled": settings.llm_enabled,
        }
    finally:
        db.close()
