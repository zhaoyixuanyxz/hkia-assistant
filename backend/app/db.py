from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine: Any = None
SessionLocal: sessionmaker | None = None


def reset_engine() -> None:
    global _engine, SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    SessionLocal = None


def init_engine(database_url: str | None = None) -> None:
    global _engine, SessionLocal
    settings = get_settings()
    url = database_url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine_kwargs: dict[str, Any] = {"connect_args": connect_args}
    if not url.startswith("sqlite"):
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_max_overflow
    try:
        _engine = create_engine(url, **engine_kwargs)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    except SQLAlchemyError:
        logger.exception("database_engine_init_failed", extra={"database_scheme": url.split(":")[0]})
        raise


def get_engine():
    if _engine is None:
        init_engine()
    return _engine


def create_tables() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator:
    if SessionLocal is None:
        init_engine()
    db = SessionLocal()  # type: ignore[misc]
    try:
        yield db
    finally:
        db.close()
