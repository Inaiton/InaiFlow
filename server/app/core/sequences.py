"""Per-org gap-free counters (``org_sequences``). The upsert takes a row lock until the transaction ends,
so concurrent callers serialize and never get the same number.

    n = await next_value(db, ctx.org_id, "NCR")          # 1, 2, 3 ...
    number = format_number("NCR-", n, 4)                  # "NCR-0001"
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def next_value(db: AsyncSession, org_id: uuid.UUID, seq_key: str) -> int:
    result = await db.execute(
        text(
            "INSERT INTO org_sequences (org_id, seq_key, next_value) VALUES (:org, :key, 2) "
            "ON CONFLICT (org_id, seq_key) DO UPDATE SET next_value = org_sequences.next_value + 1 "
            "RETURNING next_value - 1"
        ),
        {"org": org_id, "key": seq_key},
    )
    return int(result.scalar_one())


async def peek_value(db: AsyncSession, org_id: uuid.UUID, seq_key: str) -> int:
    value = (
        await db.execute(
            text("SELECT next_value FROM org_sequences WHERE org_id = :org AND seq_key = :key"),
            {"org": org_id, "key": seq_key},
        )
    ).scalar()
    return int(value) if value is not None else 1


def format_number(prefix: str | None, n: int, zero_padding: int = 4, suffix: str | None = None) -> str:
    return f"{prefix or ''}{n:0{max(zero_padding, 0)}d}{suffix or ''}"
