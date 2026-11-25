"""Identity tables: global users, refresh sessions, one-time codes, MFA recovery codes, login attempts."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.orm import (
    fk,
    flag,
    inet,
    integer,
    pk,
    string,
    textcol,
    ts,
    ts_now,
    uuid_col,
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = string(255, nullable=False, unique=True)
    password_hash: Mapped[str | None] = textcol()
    oauth_provider: Mapped[str | None] = string(50)
    oauth_subject_id: Mapped[str | None] = string(255, index=True)
    full_name: Mapped[str] = string(255, nullable=False)
    mobile: Mapped[str | None] = string(20)
    avatar_url: Mapped[str | None] = textcol()
    digital_signature_url: Mapped[str | None] = textcol()
    professional_reg_no: Mapped[str | None] = string(100)
    is_email_verified: Mapped[bool] = flag(False)
    mfa_enabled: Mapped[bool] = flag(False)
    mfa_secret: Mapped[str | None] = textcol()
    mfa_last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # TOTP replay guard
    is_suspended: Mapped[bool] = flag(False)
    avatar_storage_key: Mapped[str | None] = textcol()
    signature_storage_key: Mapped[str | None] = textcol()
    last_login_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()
    updated_at: Mapped[datetime] = ts_now()


class UserSession(Base):
    """One row per refresh token. ``family_id`` = the logical session (exposed as session id)."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, ondelete="CASCADE")
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
    replaced_by_id: Mapped[uuid.UUID | None] = fk("user_sessions.id", ondelete="SET NULL")


class AuthOneTimeCode(Base):
    __tablename__ = "auth_one_time_codes"
    __table_args__ = (Index("ix_auth_one_time_codes_email_purpose", "email", "purpose"),)

    id: Mapped[uuid.UUID] = pk()
    subject_type: Mapped[str] = string(10, nullable=False)  # USER | ADMIN
    subject_id: Mapped[uuid.UUID] = uuid_col(nullable=False, index=True)
    email: Mapped[str] = string(255, nullable=False)
    purpose: Mapped[str] = string(30, nullable=False)  # EMAIL_VERIFY | PASSWORD_RESET
    code_hash: Mapped[str] = string(64, nullable=False)
    attempts: Mapped[int] = integer(default=0)
    expires_at: Mapped[datetime] = ts(nullable=False)
    consumed_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()


class UserMfaRecoveryCode(Base):
    __tablename__ = "user_mfa_recovery_codes"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, ondelete="CASCADE")
    code_hash: Mapped[str] = textcol(nullable=False)
    used_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()


class AuthLoginAttempt(Base):
    __tablename__ = "auth_login_attempts"
    __table_args__ = (
        Index("ix_auth_login_attempts_email_created_at", "email", "created_at"),
        Index("ix_auth_login_attempts_ip_created_at", "ip", "created_at"),
    )

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str | None] = string(255)
    ip: Mapped[str | None] = inet()
    success: Mapped[bool] = flag(False)
    created_at: Mapped[datetime] = ts_now()
