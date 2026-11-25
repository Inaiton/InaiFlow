"""Organization tables: tenants, branches, sequences, memberships, invitations/join requests, audit log."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.orm import (
    fk,
    flag,
    inet,
    jsonb,
    org_fk,
    pk,
    string,
    textcol,
    ts,
    ts_now,
    uuid_col,
)

DEFAULT_SECURITY_SETTINGS = (
    '{"enforce_2fa_external": true, "enforce_2fa_all": false, "session_timeout_mins": 480, '
    '"voucher_approval_threshold": null, "require_reviewer_for_iso_docs": true}'
)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = pk()
    workspace_slug: Mapped[str] = string(100, nullable=False, unique=True)
    public_join_code: Mapped[str] = string(20, nullable=False, unique=True)
    legal_name: Mapped[str] = string(255, nullable=False)
    mailing_name: Mapped[str | None] = string(255)
    address_line1: Mapped[str] = textcol(nullable=False)
    address_line2: Mapped[str | None] = textcol()
    city: Mapped[str] = string(100, nullable=False)
    state_code: Mapped[str] = string(5, nullable=False)
    state_name: Mapped[str] = string(100, nullable=False)
    pincode: Mapped[str] = string(15, nullable=False)
    country: Mapped[str] = string(100, nullable=False, default="India")
    base_currency_code: Mapped[str] = string(10, nullable=False, default="INR")
    base_currency_symbol: Mapped[str] = string(10, nullable=False, default="₹")
    fy_begins_from: Mapped[date] = mapped_column(Date, nullable=False)
    books_beginning_from: Mapped[date] = mapped_column(Date, nullable=False)
    contact_email: Mapped[str] = string(255, nullable=False)
    contact_phone: Mapped[str] = string(30, nullable=False)
    gst_reg_type: Mapped[str] = string(50, nullable=False, default="REGULAR")
    gstin: Mapped[str | None] = string(15)
    pan: Mapped[str | None] = string(10)
    tan: Mapped[str | None] = string(10)
    cin_or_udyam: Mapped[str | None] = string(50)
    epf_code: Mapped[str | None] = string(50)
    esic_code: Mapped[str | None] = string(50)
    industry_type: Mapped[str] = string(100, nullable=False)
    iso_standard: Mapped[str | None] = string(50, default="ISO_9001_2015")
    logo_url: Mapped[str | None] = textcol()
    company_stamp_url: Mapped[str | None] = textcol()
    logo_storage_key: Mapped[str | None] = textcol()
    stamp_storage_key: Mapped[str | None] = textcol()
    plan_id: Mapped[uuid.UUID | None] = fk("platform_subscription_plans.id")
    org_status: Mapped[str] = string(30, nullable=False, default="ACTIVE")
    trial_ends_at: Mapped[datetime | None] = ts()
    security_settings: Mapped[Any] = jsonb(nullable=False, default=DEFAULT_SECURITY_SETTINGS)
    quota_overrides: Mapped[Any] = jsonb(nullable=False, default="{}")
    accounts_settings: Mapped[Any] = jsonb(nullable=False, default="{}")
    owner_user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False)
    created_at: Mapped[datetime] = ts_now()
    updated_at: Mapped[datetime] = ts_now()


class OrgBranch(Base):
    __tablename__ = "org_branches"
    __table_args__ = (UniqueConstraint("org_id", "name"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = string(200, nullable=False)
    address: Mapped[str | None] = textcol()
    state_code: Mapped[str | None] = string(5)
    gstin: Mapped[str | None] = string(15)
    is_head_office: Mapped[bool] = flag(False)
    created_at: Mapped[datetime] = ts_now()


class OrgSequence(Base):
    __tablename__ = "org_sequences"
    __table_args__ = (PrimaryKeyConstraint("org_id", "seq_key"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    seq_key: Mapped[str] = string(100, nullable=False)
    next_value: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))


class OrgMembership(Base):
    __tablename__ = "org_memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, ondelete="CASCADE")
    role_id: Mapped[uuid.UUID] = fk("org_roles.id", nullable=False)
    status: Mapped[str] = string(30, nullable=False, default="ACTIVE")  # ACTIVE|SUSPENDED|REVOKED|EXPIRED
    access_expires_at: Mapped[datetime | None] = ts()
    joined_at: Mapped[datetime] = ts_now()


class OrgInvitationOrRequest(Base):
    __tablename__ = "org_invitations_and_requests"
    __table_args__ = (
        Index("ix_org_invitations_and_requests_org_id_status", "org_id", "status"),
        Index("ix_org_invitations_and_requests_email", "email"),
    )

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    flow_type: Mapped[str] = string(20, nullable=False)  # INVITE_PUSH | JOIN_REQUEST_PULL
    email: Mapped[str] = string(255, nullable=False)
    user_id: Mapped[uuid.UUID | None] = fk("users.id")
    proposed_role_id: Mapped[uuid.UUID | None] = fk("org_roles.id")
    token_hash: Mapped[str | None] = textcol()
    status: Mapped[str] = string(20, nullable=False, default="PENDING")  # PENDING|ACCEPTED|REJECTED|EXPIRED|CANCELLED
    access_expires_at: Mapped[datetime | None] = ts()
    created_by: Mapped[uuid.UUID | None] = fk("users.id")
    expires_at: Mapped[datetime] = ts(nullable=False)
    message: Mapped[str | None] = textcol()
    acl_grants: Mapped[Any] = jsonb()
    decided_by: Mapped[uuid.UUID | None] = fk("users.id")
    decided_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()


class OrgAuditLog(Base):
    """Append-only (trigger blocks UPDATE/DELETE; app role has SELECT+INSERT only)."""

    __tablename__ = "org_audit_logs"
    __table_args__ = (
        Index("ix_org_audit_logs_org_id_created_at", "org_id", "created_at"),
        Index("ix_org_audit_logs_org_id_entity", "org_id", "entity_type", "entity_id"),
    )

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = fk("users.id")
    actor_type: Mapped[str] = string(20, nullable=False, default="USER")  # USER|SYSTEM|PLATFORM_ADMIN
    actor_id: Mapped[uuid.UUID | None] = uuid_col()
    role_code: Mapped[str] = string(50, nullable=False)
    module: Mapped[str] = string(30, nullable=False)
    action: Mapped[str] = string(30, nullable=False)
    entity_type: Mapped[str] = string(100, nullable=False)
    entity_id: Mapped[uuid.UUID] = uuid_col(nullable=False)
    before_diff: Mapped[Any] = jsonb()
    after_diff: Mapped[Any] = jsonb()
    reason: Mapped[str | None] = textcol()
    ip_address: Mapped[str | None] = inet()
    created_at: Mapped[datetime] = ts_now()
