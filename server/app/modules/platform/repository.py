"""Platform data access (configs, versions, plans). Never commits."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.models import PlatformGlobalConfig, PlatformGlobalConfigVersion, PlatformSubscriptionPlan


async def config_payload(db: AsyncSession, category: str, key: str, on_date: date | None) -> dict | None:
    cfg = (
        await db.execute(
            select(PlatformGlobalConfig.id, PlatformGlobalConfig.payload, PlatformGlobalConfig.is_active).where(
                PlatformGlobalConfig.config_category == category, PlatformGlobalConfig.config_key == key
            )
        )
    ).first()
    if cfg is None or not cfg.is_active:
        return None
    if on_date is None:
        return cfg.payload
    version = (
        await db.execute(
            select(PlatformGlobalConfigVersion.payload)
            .where(
                PlatformGlobalConfigVersion.config_id == cfg.id,
                or_(
                    PlatformGlobalConfigVersion.effective_from.is_(None),
                    PlatformGlobalConfigVersion.effective_from <= on_date,
                ),
            )
            .order_by(PlatformGlobalConfigVersion.effective_from.desc().nulls_last(),
                      PlatformGlobalConfigVersion.version.desc())
            .limit(1)
        )
    ).scalar()  # fmt: skip
    return version if version is not None else cfg.payload


async def config_keys(db: AsyncSession, category: str) -> list[str]:
    rows = await db.execute(
        select(PlatformGlobalConfig.config_key)
        .where(PlatformGlobalConfig.config_category == category, PlatformGlobalConfig.is_active)
        .order_by(PlatformGlobalConfig.config_key)
    )
    return list(rows.scalars())


async def plan_by_id(db: AsyncSession, plan_id: uuid.UUID) -> PlatformSubscriptionPlan | None:
    return await db.get(PlatformSubscriptionPlan, plan_id)


async def plan_by_code(db: AsyncSession, code: str) -> PlatformSubscriptionPlan | None:
    return (
        await db.execute(select(PlatformSubscriptionPlan).where(PlatformSubscriptionPlan.plan_code == code))
    ).scalar_one_or_none()
