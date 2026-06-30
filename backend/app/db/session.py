"""SQLAlchemy session/engine setup against Supabase Postgres.

Engine creation is deferred until first use so that importing models (e.g. in
tests) does not require DATABASE_URL to be configured.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.core.config import settings


class Base(DeclarativeBase):
    pass


@lru_cache
def _engine():
    return create_engine(
        settings.sqlalchemy_url,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache
def _session_factory():
    return sessionmaker(bind=_engine(), autoflush=False, autocommit=False, class_=Session)


def get_engine():
    return _engine()


def get_db() -> Generator[Session, None, None]:
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()


# Backwards-compatible names used elsewhere in the app.
def SessionLocal() -> Session:  # noqa: N802 - keep worker import working
    return _session_factory()()


# Keep a module-level `engine` alias for code that references it directly; it is
# resolved lazily through property access to avoid import-time connection setup.
class _LazyEngine:
    def __getattr__(self, name):
        return getattr(_engine(), name)


engine = _LazyEngine()