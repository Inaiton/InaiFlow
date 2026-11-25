"""Operations tables: workflow templates (versioned), period runs, steps, voucher links, NCR/CAPA,
calibration instruments, ISO 9001 checklist."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.orm import (
    fk,
    flag,
    integer,
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


class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"
    __table_args__ = (UniqueConstraint("org_id", "template_key", "version"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    template_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, server_default=text("gen_random_uuid()"), index=True
    )
    stock_item_id: Mapped[uuid.UUID | None] = fk("stock_items.id")
    name: Mapped[str] = string(200, nullable=False)
    description: Mapped[str | None] = textcol()
    iso_clause_ref: Mapped[str | None] = string(100)
    version: Mapped[int] = integer(default=1)
    status: Mapped[str] = string(20, nullable=False, default="DRAFT")  # DRAFT | PUBLISHED | ARCHIVED
    is_published: Mapped[bool] = flag(False)
    published_at: Mapped[datetime | None] = ts()
    graph_definition: Mapped[Any] = jsonb(nullable=False)
    created_by: Mapped[uuid.UUID] = fk("users.id", nullable=False)
    created_at: Mapped[datetime] = ts_now()
    updated_at: Mapped[datetime] = ts_now()


class PeriodRun(Base):
    __tablename__ = "period_runs"
    __table_args__ = (Index("ix_period_runs_org_id_period_month", "org_id", "period_month"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    workflow_template_id: Mapped[uuid.UUID] = fk("workflow_templates.id", nullable=False)
    workflow_version: Mapped[int] = integer()
    graph_snapshot: Mapped[Any] = jsonb()
    stock_item_id: Mapped[uuid.UUID | None] = fk("stock_items.id")
    cost_centre_id: Mapped[uuid.UUID | None] = fk("cost_centres.id")
    doc_folder_id: Mapped[uuid.UUID | None] = uuid_col()
    mfg_voucher_id: Mapped[uuid.UUID | None] = fk("vouchers.id")
    run_title: Mapped[str] = string(200, nullable=False)
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    planned_qty: Mapped[Decimal] = money(default=None)
    accepted_qty: Mapped[Decimal] = money()
    rejected_qty: Mapped[Decimal] = money()
    rework_qty: Mapped[Decimal] = money()
    status: Mapped[str] = string(30, nullable=False, default="IN_PROGRESS")
    hold_reason: Mapped[str | None] = textcol()
    cancel_reason: Mapped[str | None] = textcol()
    total_debit_cost: Mapped[Decimal] = money()
    total_credit_recovery: Mapped[Decimal] = money()
    computed_unit_cost: Mapped[Decimal] = money()
    created_by: Mapped[uuid.UUID] = fk("users.id", nullable=False)
    started_at: Mapped[datetime | None] = ts()
    completed_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()


class PeriodRunStep(Base):
    __tablename__ = "period_run_steps"
    __table_args__ = (UniqueConstraint("period_run_id", "node_id"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    period_run_id: Mapped[uuid.UUID] = fk("period_runs.id", nullable=False, ondelete="CASCADE")
    node_id: Mapped[str] = string(100, nullable=False)
    step_name: Mapped[str] = string(200, nullable=False)
    node_shape: Mapped[str] = string(30, nullable=False)
    sequence: Mapped[int] = integer(default=0)
    input_qty: Mapped[Decimal | None] = money(nullable=True)
    accepted_qty: Mapped[Decimal | None] = money(nullable=True)
    rejected_qty: Mapped[Decimal | None] = money(nullable=True)
    rework_qty: Mapped[Decimal] = money()
    qc_measurements: Mapped[Any] = jsonb(default="{}")
    branch_taken: Mapped[str | None] = string(50)
    status: Mapped[str] = string(30, nullable=False, default="PENDING")
    quick_qc: Mapped[bool] = flag(False)
    is_locked: Mapped[bool] = flag(False)
    executed_by: Mapped[uuid.UUID | None] = fk("users.id")
    executed_at: Mapped[datetime | None] = ts()
    instrument_id: Mapped[uuid.UUID | None] = fk("calibration_instruments.id")
    notes: Mapped[str | None] = textcol()
    skip_reason: Mapped[str | None] = textcol()
    signed_off_by: Mapped[uuid.UUID | None] = fk("users.id")
    signed_off_at: Mapped[datetime | None] = ts()
    override_reason: Mapped[str | None] = textcol()


class PeriodRunVoucherLink(Base):
    __tablename__ = "period_run_voucher_links"
    __table_args__ = (UniqueConstraint("period_run_id", "voucher_id"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    period_run_id: Mapped[uuid.UUID] = fk("period_runs.id", nullable=False, ondelete="CASCADE")
    voucher_id: Mapped[uuid.UUID] = fk("vouchers.id", nullable=False, ondelete="CASCADE")
    step_id: Mapped[uuid.UUID | None] = fk("period_run_steps.id", ondelete="SET NULL")
    linked_by: Mapped[uuid.UUID | None] = fk("users.id")
    created_at: Mapped[datetime] = ts_now()


class IsoNcrCapaRecord(Base):
    __tablename__ = "iso_ncr_capa_records"
    __table_args__ = (UniqueConstraint("org_id", "ncr_number"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    ncr_number: Mapped[str] = string(50, nullable=False)
    period_run_id: Mapped[uuid.UUID | None] = fk("period_runs.id")
    run_step_id: Mapped[uuid.UUID | None] = fk("period_run_steps.id")
    rejected_qty: Mapped[Decimal] = money(default=None)
    defect_description: Mapped[str] = textcol(nullable=False)
    root_cause_analysis: Mapped[str | None] = textcol()
    corrective_action: Mapped[str | None] = textcol()
    preventive_action: Mapped[str | None] = textcol()
    verification_notes: Mapped[str | None] = textcol()
    source: Mapped[str] = string(20, nullable=False, default="MANUAL")  # MANUAL | AUTO_QC
    status: Mapped[str] = string(30, nullable=False, default="OPEN")
    assigned_to: Mapped[uuid.UUID | None] = fk("users.id")
    closed_by: Mapped[uuid.UUID | None] = fk("users.id")
    closed_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = ts_now()


class CalibrationInstrument(Base):
    __tablename__ = "calibration_instruments"
    __table_args__ = (UniqueConstraint("org_id", "instrument_code"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    instrument_code: Mapped[str] = string(100, nullable=False)
    name: Mapped[str] = string(200, nullable=False)
    location: Mapped[str | None] = string(200)
    range_spec: Mapped[str | None] = string(100)
    least_count: Mapped[str | None] = string(50)
    last_calibrated_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    certificate_doc_id: Mapped[uuid.UUID | None] = uuid_col()
    status: Mapped[str] = string(30, nullable=False, default="VALID")  # VALID | DUE_SOON | EXPIRED
    created_at: Mapped[datetime] = ts_now()


class IsoChecklistItem(Base):
    __tablename__ = "iso_checklist_items"
    __table_args__ = (UniqueConstraint("org_id", "clause", "title"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    clause: Mapped[str] = string(20, nullable=False)
    title: Mapped[str] = string(255, nullable=False)
    description: Mapped[str | None] = textcol()
    sort_order: Mapped[int] = integer(default=0)
    status: Mapped[str] = string(20, nullable=False, default="NOT_STARTED")
    evidence_document_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("'{}'::uuid[]")
    )
    notes: Mapped[str | None] = textcol()
    updated_by: Mapped[uuid.UUID | None] = fk("users.id")
    updated_at: Mapped[datetime | None] = ts()


class PeriodRunCostLine(Base):
    """Run-level money-flow lines owned by operations (S4, migration 0004): payroll allocations
    (``source=PAYROLL``) and Dr/Cr postings made from the run page (``source=POSTING``, with voucher_id)."""

    __tablename__ = "period_run_cost_lines"

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    period_run_id: Mapped[uuid.UUID] = fk("period_runs.id", nullable=False, ondelete="CASCADE")
    step_id: Mapped[uuid.UUID | None] = fk("period_run_steps.id", ondelete="SET NULL")
    voucher_id: Mapped[uuid.UUID | None] = fk("vouchers.id", ondelete="SET NULL")
    source: Mapped[str] = string(20, nullable=False)  # PAYROLL | POSTING
    entry_type: Mapped[str] = string(2, nullable=False)  # DR | CR
    amount: Mapped[Decimal] = money(default=None)
    line_date: Mapped[date] = mapped_column(Date, nullable=False)
    particulars: Mapped[str] = textcol(nullable=False)
    created_by: Mapped[uuid.UUID | None] = fk("users.id")
    created_at: Mapped[datetime] = ts_now()
