"""Async engine, declarative Base, sessions and the RLS tenant-scope helper."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

APP_ROLE = "inaiflow_app"

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def to_dict(self) -> dict[str, Any]:
        """Column values keyed by attribute name (for audit before/after snapshots)."""
        return {c.key: getattr(self, c.key) for c in self.__mapper__.column_attrs}


def normalize_async_url(url: str) -> tuple[str, dict[str, Any]]:
    """Accept postgres:// / postgresql:// URLs, force asyncpg, translate sslmode -> connect_args."""
    connect_args: dict[str, Any] = {}
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    if sslmode in ("require", "verify-ca", "verify-full"):
        connect_args["ssl"] = "require"
    return urlunsplit(parts._replace(query=urlencode(query))), connect_args


def is_pooler_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.port == 6543 or "pooler.supabase.com" in (parts.hostname or "")


@lru_cache
def get_engine() -> AsyncEngine:
    s = get_settings()
    url, connect_args = normalize_async_url(s.DATABASE_URL)
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if is_pooler_url(url) or s.use_nullpool:
        # Supabase transaction pooler (pgbouncer): no server-side prepared statement reuse.
        connect_args.update(
            statement_cache_size=0,
            prepared_statement_cache_size=0,
            prepared_statement_name_func=lambda: f"__asyncpg_{uuid.uuid4()}__",
        )
    if s.use_nullpool:
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = s.DB_POOL_SIZE
    return create_async_engine(url, connect_args=connect_args, **kwargs)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=True)


async def set_tenant_scope(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
    """Switch the *current transaction* to the RLS app role for ``org_id``.

    Must be called inside an open transaction; ``SET LOCAL``/``set_config(..., true)`` end with it.
    """
    await db.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    await db.execute(
        text("SELECT set_config('app.current_org_id', :org, true), set_config('app.current_user_id', :usr, true)"),
        {"org": str(org_id), "usr": str(user_id) if user_id else ""},
    )


@asynccontextmanager
async def independent_session() -> AsyncIterator[AsyncSession]:
    """A separate session+transaction that commits on exit even if the request later fails.

    Use for writes that must survive a failing request (failed-login attempts, code attempt counters).
    """
    async with get_sessionmaker()() as session, session.begin():
        yield session


async def db_now(db: AsyncSession) -> datetime:
    return (await db.execute(text("SELECT now()"))).scalar_one()
