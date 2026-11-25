"""Platform administration tables (separate identity from tenant users)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.orm import (
    fk,
    flag,
    inet,
    jsonb,
    money,
    org_fk,
    pk,
    string,
    textcol,
    ts,
    ts_now,
    uuid_col,
)


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = string(255, nullable=False, unique=True)
    password_hash: Mapped[str] = textcol(nullable=False)
    full_name: Mapped[str] = string(255, nullable=False)
    role: Mapped[str] = string(50, nullable=False, default="SUPERADMIN")
    is_active: Mapped[bool] = flag(True)
    mfa_secret: Mapped[str | None] = textcol()
    mfa_last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # TOTP replay guard
    mfa_enabled: Mapped[bool] = flag(False)
    must_change_password: Mapped[bool] = flag(False)
    last_login_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[uuid.UUID] = pk()
    admin_id: Mapped[uuid.UUID] = fk("platform_admins.id", nullable=False, ondelete="CASCADE")
    family_id: Mapped[uuid.UUID] = uuid_col(nullable=False, index=True)
    token_hash: Mapped[str] = string(64, nullable=False, unique=True)
    user_agent: Mapped[str | None] = textcol()
    ip: Mapped[str | None] = inet()
    remember: Mapped[bool] = flag(False)
    created_at: Mapped[datetime] = ts_now()
    last_used_at: Mapped[datetime] = ts_now()
    expires_at: Mapped[datetime] = ts(nullable=False)
    revoked_at: Mapped[datetime | None] = ts()
    revoke_reason: Mapped[str | None] = string(30)
    replaced_by_id: Mapped[uuid.UUID | None] = fk("admin_sessions.id", ondelete="SET NULL")


class PlatformAuditLog(Base):
    """Append-only (trigger blocks UPDATE/DELETE)."""

    __tablename__ = "platform_audit_logs"
    __table_args__ = (
        Index("ix_platform_audit_logs_created_at", "created_at"),
        Index("ix_platform_audit_logs_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = pk()
    superadmin_id: Mapped[uuid.UUID | None] = fk("platform_admins.id")
    action: Mapped[str] = string(100, nullable=False)
    target_type: Mapped[str] = string(100, nullable=False)
    target_id: Mapped[uuid.UUID | None] = uuid_col()
    before_state: Mapped[Any] = jsonb()
    after_state: Mapped[Any] = jsonb()
    ip_address: Mapped[str | None] = inet()
    created_at: Mapped[datetime] = ts_now()


class PlatformSubscriptionInvoice(Base):
    __tablename__ = "platform_subscription_invoices"

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    invoice_number: Mapped[str] = string(50, nullable=False, unique=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount_inr: Mapped[Decimal] = money()
    status: Mapped[str] = string(10, nullable=False, default="DUE")  # DUE | PAID | VOID
    paid_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()


class PlatformImpersonationSession(Base):
    __tablename__ = "platform_impersonation_sessions"

    id: Mapped[uuid.UUID] = pk()
    admin_id: Mapped[uuid.UUID] = fk("platform_admins.id", nullable=False)
    org_id: Mapped[uuid.UUID] = org_fk()
    mode: Mapped[str] = string(20, nullable=False)  # READ_ONLY | FULL_SUPPORT
    ticket_reference: Mapped[str] = string(100, nullable=False)
    reason: Mapped[str] = textcol(nullable=False)
    expires_at: Mapped[datetime] = ts(nullable=False)
    created_at: Mapped[datetime] = ts_now()
    ended_at: Mapped[datetime | None] = ts()
