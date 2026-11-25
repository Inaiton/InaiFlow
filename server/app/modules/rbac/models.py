"""RBAC tables: per-org roles (permission matrix JSON) and record-level ACL overrides."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped

from app.core.db import Base
from app.core.orm import flag, jsonb, org_fk, pk, string, ts_now, uuid_col


class OrgRole(Base):
    __tablename__ = "org_roles"
    __table_args__ = (UniqueConstraint("org_id", "role_code"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    role_code: Mapped[str] = string(50, nullable=False)
    role_name: Mapped[str] = string(100, nullable=False)
    is_system_role: Mapped[bool] = flag(False)
    is_external_collaborator: Mapped[bool] = flag(False)
    permissions: Mapped[Any] = jsonb(nullable=False, default="{}")
    created_at: Mapped[datetime] = ts_now()


class ResourceAcl(Base):
    __tablename__ = "resource_acl"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "subject_type",
            "subject_id",
            "resource_type",
            "resource_id",
            name="uq_resource_acl_subject_resource",
        ),
        Index("ix_resource_acl_org_id_resource", "org_id", "resource_type", "resource_id"),
        Index("ix_resource_acl_org_id_subject", "org_id", "subject_type", "subject_id"),
    )

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    subject_type: Mapped[str] = string(20, nullable=False)  # ROLE | USER
    subject_id: Mapped[uuid.UUID] = uuid_col(nullable=False)
    resource_type: Mapped[str] = string(50, nullable=False)  # STOCK_ITEM | PERIOD_RUN | DOC_FOLDER | GODOWN
    resource_id: Mapped[uuid.UUID] = uuid_col(nullable=False)
    access_level: Mapped[str] = string(20, nullable=False)  # NONE | READ | WRITE | FULL
    created_at: Mapped[datetime] = ts_now()
