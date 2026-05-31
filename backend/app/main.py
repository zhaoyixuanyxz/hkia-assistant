"""HKIA API — Phase 2 infrastructure (LangGraph, RAG hooks, Postgres-ready)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app import db as db_mod
from app.routers import admin, auth, conversations, knowledge, market, meta, users

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")


def _cors_origins() -> list[str]:
    raw = get_settings().cors_origins
    return [o.strip() for o in raw.split(",") if o.strip()]


def promote_bootstrap_admins() -> None:
    raw = get_settings().admin_bootstrap_emails
    emails = {e.strip().lower() for e in raw.replace(";", ",").split(",") if e.strip()}
    if not emails or db_mod.SessionLocal is None:
        return
    from sqlalchemy import select

    from app.models import User

    db = db_mod.SessionLocal()
    try:
        for user in db.scalars(select(User).where(User.email.in_(emails))).all():
            user.role = "admin"
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.checkpoint.postgres import PostgresSaver

    from app.logging_config import configure_logging

    configure_logging()

    settings = get_settings()
    if settings.langchain_tracing_v2 and (settings.langchain_api_key or "").strip():
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key.strip()
        if (settings.langchain_project or "").strip():
            os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project.strip()

    from app import db as db_mod

    if db_mod.SessionLocal is None:
        db_mod.init_engine()
    db_mod.create_tables()

    promote_bootstrap_admins()


    cp_cm = None
    graph_cp: Any = MemorySaver()
    url = settings.database_url
    if (
        not url.startswith("sqlite")
        and not settings.force_memory_checkpointer
    ):
        conn = url.replace("postgresql+psycopg://", "postgresql://", 1)
        cp_cm = PostgresSaver.from_conn_string(conn)
        graph_cp = cp_cm.__enter__()
        graph_cp.setup()

    app.state.graph_checkpointer_cm = cp_cm
    app.state.graph_checkpointer = graph_cp

    yield

    if cp_cm is not None:
        cp_cm.__exit__(None, None, None)


app = FastAPI(title="HKIA API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(meta.router)
app.include_router(users.router)
app.include_router(conversations.router)
app.include_router(knowledge.router)
app.include_router(market.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
