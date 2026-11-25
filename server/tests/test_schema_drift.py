"""SQLAlchemy metadata must match the migrated database exactly (alembic autogenerate diff is empty)."""

import asyncio

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.all_models import metadata


def _diff(sync_conn):  # noqa: ANN001,ANN202
    ctx = MigrationContext.configure(
        sync_conn,
        opts={
            "compare_type": True,
            "include_object": lambda o, n, t, r, c: not (t == "table" and n == "alembic_version"),
        },
    )
    return compare_metadata(ctx, metadata)


def test_models_match_database(database):
    async def run():  # noqa: ANN202
        engine = create_async_engine(database, poolclass=NullPool)
        async with engine.connect() as conn:
            diff = await conn.run_sync(_diff)
        await engine.dispose()
        return diff

    diff = asyncio.run(run())
    assert diff == [], diff
