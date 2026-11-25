"""Org-creation seeding for operations: ISO 9001:2015 checklist items (workflow library stays global)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.modules.operations.models import IsoChecklistItem
from app.modules.platform.interface import get_config


async def seed_org_operations(db: AsyncSession, ctx: TenantContext) -> int:
    items = (await get_config(db, "ISO_CHECKLIST", "ISO_9001_2015"))["items"]
    for i, item in enumerate(items):
        db.add(IsoChecklistItem(org_id=ctx.org_id, clause=item["clause"], title=item["title"],
                                description=item.get("description"), sort_order=i))  # fmt: skip
    await db.flush()
    return len(items)
