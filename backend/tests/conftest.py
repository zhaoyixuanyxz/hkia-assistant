from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db as db_mod
from app.config import get_settings
from app.db import get_db
from app.embeddings import reset_embedding_singleton
from app.llm import MockLLM
from app.main import app
from app.routers.conversations import get_llm_dep


@pytest.fixture(autouse=True)
def _isolate_external_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.setenv("QDRANT_URL", "")
    monkeypatch.setenv("EMBEDDING_API_KEY", "")
    monkeypatch.setenv("EMBEDDING_API_BASE", "")
    get_settings.cache_clear()
    reset_embedding_singleton()


@pytest.fixture
def api_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv(
        "JWT_SECRET", "test-secret-key-for-pytest-at-least-32-bytes-long"
    )
    sqlite_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    get_settings.cache_clear()
    db_mod.reset_engine()
    db_mod.init_engine(sqlite_url)
    db_mod.create_tables()

    def _db():
        s = db_mod.SessionLocal()  # type: ignore[misc]
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_llm_dep] = lambda: MockLLM()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    db_mod.reset_engine()
    get_settings.cache_clear()
