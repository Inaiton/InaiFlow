"""Documents tables: FY/month folder tree, report & folder-rule templates, documents (ISO 7.5)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Computed, Date, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.orm import (
    fk,
    flag,
    integer,
    jsonb,
    org_fk,
    pk,
    string,
    textcol,
    ts,
    ts_now,
)

SEARCH_TSV_EXPR = (
    "to_tsvector('simple'::regconfig, "
    "coalesce(title, '') || ' ' || coalesce(iso_doc_number, '') || ' ' || "
    "coalesce(file_name, '') || ' ' || coalesce(ocr_text, ''))"
)


class DocFolder(Base):
    __tablename__ = "doc_folders"
    __table_args__ = (UniqueConstraint("org_id", "parent_folder_id", "name", postgresql_nulls_not_distinct=True),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    parent_folder_id: Mapped[uuid.UUID | None] = fk("doc_folders.id", ondelete="CASCADE")
    name: Mapped[str] = string(200, nullable=False)
    system_kind: Mapped[str | None] = string(30)
    fy_label: Mapped[str | None] = string(20)
    month_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_system_locked: Mapped[bool] = flag(False)
    linked_period_run_id: Mapped[uuid.UUID | None] = fk("period_runs.id")
    created_at: Mapped[datetime] = ts_now()


class DocTemplate(Base):
    __tablename__ = "doc_templates"

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    template_type: Mapped[str] = string(30, nullable=False)  # REPORT_DOC | MONTHLY_FOLDER_RULE
    name: Mapped[str] = string(200, nullable=False)
    description: Mapped[str | None] = textcol()
    system_key: Mapped[str | None] = string(100)  # platform config key it was seeded from
    is_system_default: Mapped[bool] = flag(False)
    content_schema: Mapped[Any] = jsonb(nullable=False)
    created_by: Mapped[uuid.UUID | None] = fk("users.id")
    created_at: Mapped[datetime] = ts_now()
    updated_at: Mapped[datetime] = ts_now()


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_search_tsv", "search_tsv", postgresql_using="gin"),
        Index("ix_documents_org_id_iso_doc_number", "org_id", "iso_doc_number"),
    )

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    folder_id: Mapped[uuid.UUID] = fk("doc_folders.id", nullable=False)
    title: Mapped[str] = string(255, nullable=False)
    source_type: Mapped[str] = string(30, nullable=False)
    file_name: Mapped[str | None] = string(255)
    file_mime_type: Mapped[str | None] = string(100)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = string(64)
    storage_key: Mapped[str | None] = textcol()
    upload_status: Mapped[str] = string(20, nullable=False, default="READY")  # PENDING | READY
    rich_content: Mapped[Any] = jsonb()
    ocr_text: Mapped[str | None] = textcol()
    search_tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed(SEARCH_TSV_EXPR, persisted=True))
    template_id: Mapped[uuid.UUID | None] = fk("doc_templates.id", ondelete="SET NULL")
    iso_doc_number: Mapped[str | None] = string(100)
    revision_no: Mapped[int] = integer(default=1)
    previous_revision_id: Mapped[uuid.UUID | None] = fk("documents.id", ondelete="SET NULL")
    approval_status: Mapped[str] = string(30, nullable=False, default="DRAFT")
    review_comment: Mapped[str | None] = textcol()
    linked_voucher_id: Mapped[uuid.UUID | None] = fk("vouchers.id")
    linked_period_run_id: Mapped[uuid.UUID | None] = fk("period_runs.id")
    linked_step_id: Mapped[uuid.UUID | None] = fk("period_run_steps.id")
    linked_stock_item_id: Mapped[uuid.UUID | None] = fk("stock_items.id")
    prepared_by: Mapped[uuid.UUID] = fk("users.id", nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = fk("users.id")
    approved_by: Mapped[uuid.UUID | None] = fk("users.id")
    approved_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()
    updated_at: Mapped[datetime] = ts_now()
