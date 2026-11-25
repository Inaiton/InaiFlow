"""Platform tables: effective-dated global configs, subscription plans, idempotency keys."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.orm import fk, flag, integer, jsonb, money, pk, string, textcol, ts_now


class PlatformGlobalConfig(Base):
    __tablename__ = "platform_global_configs"
    __table_args__ = (UniqueConstraint("config_category", "config_key"),)

    id: Mapped[uuid.UUID] = pk()
    config_category: Mapped[str] = string(100, nullable=False)
    config_key: Mapped[str] = string(150, nullable=False)
    display_name: Mapped[str] = string(255, nullable=False)
    payload: Mapped[Any] = jsonb(nullable=False)
    version: Mapped[int] = integer(default=1)
    is_active: Mapped[bool] = flag(True)
    updated_by: Mapped[uuid.UUID | None] = fk("platform_admins.id")
    updated_at: Mapped[datetime] = ts_now()


class PlatformGlobalConfigVersion(Base):
    __tablename__ = "platform_global_config_versions"
    __table_args__ = (UniqueConstraint("config_id", "version"),)

    id: Mapped[uuid.UUID] = pk()
    config_id: Mapped[uuid.UUID] = fk("platform_global_configs.id", nullable=False, ondelete="CASCADE")
    version: Mapped[int] = integer()
    payload: Mapped[Any] = jsonb(nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    change_reason: Mapped[str | None] = textcol()
    created_by: Mapped[uuid.UUID | None] = fk("platform_admins.id")
    created_at: Mapped[datetime] = ts_now()


class PlatformSubscriptionPlan(Base):
    __tablename__ = "platform_subscription_plans"

    id: Mapped[uuid.UUID] = pk()
    plan_code: Mapped[str] = string(50, nullable=False, unique=True)
    name: Mapped[str] = string(100, nullable=False)
    monthly_price_inr: Mapped[Decimal] = money(default=None)
    annual_price_inr: Mapped[Decimal] = money(default=None)
    max_internal_seats: Mapped[int] = integer()
    max_external_collaborators: Mapped[int] = integer()
    max_storage_gb: Mapped[int] = integer()
    enabled_modules: Mapped[Any] = jsonb(nullable=False)
    is_active: Mapped[bool] = flag(True)
    created_at: Mapped[datetime] = ts_now()


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        PrimaryKeyConstraint("org_id", "user_id", "key"),
        Index("ix_idempotency_keys_created_at", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = string(255, nullable=False)
    request_hash: Mapped[str] = string(64, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Any] = jsonb()
    created_at: Mapped[datetime] = ts_now()
