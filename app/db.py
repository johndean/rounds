"""
Async SQLAlchemy session factory.

The app talks to Postgres via asyncpg. Settings.DATABASE_URL is normalized
to the `postgresql+asyncpg://` scheme upstream (see config.py validator).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.x declarative base for all ORM models."""


# In tests, pytest-asyncio runs each test on its own event loop. A pooled
# asyncpg connection created on loop A and reused on loop B raises "got Future
# attached to a different loop" / "Event loop is closed". NullPool opens a fresh
# connection per checkout and closes it on return, so nothing is reused across
# loops — the DB-integration suite (split/merge/inverse/reorder) needs this to
# run at all. Production keeps the real pool.
if settings.ENVIRONMENT == "test":
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
    )

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an AsyncSession bound to the request scope."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


DbSession = Annotated[AsyncSession, Depends(get_session)]
