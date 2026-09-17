import os
import sys
from pathlib import Path


backend_dir = Path(__file__).resolve().parents[2] / "src" / "backend"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CPF_ENCRYPTION_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


import pytest


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app import main
    from app.database import Base, get_db

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with testing_session() as session:
            yield session

    # Startup and requests must both use this test's in-memory database.
    monkeypatch.setattr(main, "SessionLocal", testing_session)
    monkeypatch.setattr(main.app.state, "session_factory", testing_session)
    monkeypatch.setattr(main.app, "dependency_overrides", {
        **main.app.dependency_overrides,
        get_db: override_db,
    })
    try:
        Base.metadata.create_all(engine)
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        engine.dispose()
