# app/db/session.py
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from .models import *  # ensure models are imported for metadata


# -------------------------
# Database URL & engine
# -------------------------

def _default_db_url() -> str:
    """
    Choose a sensible default:
    - Async SQLite in local file (dev): sqlite+aiosqlite:///./health_chat.db
    - Can be overridden with DATABASE_URL (supports PostgreSQL, etc.)
    """
    return "sqlite+aiosqlite:///./health_chat.db"


DATABASE_URL = os.getenv("DATABASE_URL", _default_db_url())

# Create async engine
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "0") == "1",
    pool_pre_ping=True,
    future=True,
)


# -------------------------
# Session factory (async)
# -------------------------

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """
    Async transactional scope. Use in services where you want explicit control:

        async with session_scope() as session:
            ... do work ...
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# -------------------------
# FastAPI dependency
# -------------------------

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to inject a DB session:

        @app.get("/...")
        async def handler(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            # session is auto-closed on exit
            ...


# -------------------------
# Schema management
# -------------------------

async def init_db() -> None:
    """Create all tables if they do not exist (dev/local usage)."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def drop_db() -> None:
    """Drop all tables (useful for test reset)."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
