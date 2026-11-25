"""Alembic environment (async, asyncpg).

URL precedence: ``-x url=...`` > ``DATABASE_URL_MIGRATIONS`` > ``DATABASE_URL``. Use the Supabase *session*
pooler (5432) or a direct connection for migrations, never the transaction pooler.
"""

from __future__ import annotations

import asyncio
import os

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.all_models import metadata
from app.core.db import normalize_async_url

config = context.config
target_metadata = metadata


def _url() -> str:
    x = context.get_x_argument(as_dictionary=True)
    url = x.get("url") or os.environ.get("DATABASE_URL_MIGRATIONS") or os.environ.get("DATABASE_URL")
    if not url:
        from app.core.config import get_settings

        s = get_settings()
        url = s.DATABASE_URL_MIGRATIONS or s.DATABASE_URL
    return url


def include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001
    # alembic_version is managed by alembic itself
    return not (type_ == "table" and name == "alembic_version")


def run_migrations_offline() -> None:
    url, _ = normalize_async_url(_url())
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url, connect_args = normalize_async_url(_url())
    engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
