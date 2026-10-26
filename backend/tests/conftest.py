from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("OPENAI_API_KEY", "")  # force demo mode in tests


@pytest.fixture()
def client(monkeypatch):
    from app import database
    from app.database import Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}, future=True
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSession)
    # patch references already imported elsewhere
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "engine", engine)
    monkeypatch.setattr(main_mod, "SessionLocal", TestingSession)

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    from app.main import app

    app.dependency_overrides[database.get_db] = override_get_db

    # seed the demo profile + sample academic data (tests rely on fixtures)
    db = TestingSession()
    from app.seed import ensure_profile, seed_sample_data
    ensure_profile(db)
    seed_sample_data(db)
    db.close()

    with TestClient(app) as c:
        c._SessionLocal = TestingSession  # expose for direct DB use
        yield c

    app.dependency_overrides.clear()
    os.remove(path)


@pytest.fixture()
def db_session(client):
    session = client._SessionLocal()
    try:
        yield session
    finally:
        session.close()
