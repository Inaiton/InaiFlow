"""Taxation tables: GSTR-2B imports and IRP e-invoice / e-way bill records."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index
from sqlalchemy.orm import Mapped

from app.core.db import Base
from app.core.orm import fk, jsonb, org_fk, pk, string, textcol, ts, ts_now


class Gst2bImport(Base):
    __tablename__ = "gst_2b_imports"
    __table_args__ = (Index("ix_gst_2b_imports_org_id_period", "org_id", "period"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    period: Mapped[str] = string(7, nullable=False)  # YYYY-MM
    payload: Mapped[Any] = jsonb(nullable=False)
    imported_by: Mapped[uuid.UUID | None] = fk("users.id")
    created_at: Mapped[datetime] = ts_now()


class EinvoiceRecord(Base):
    __tablename__ = "einvoice_records"

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    voucher_id: Mapped[uuid.UUID] = fk("vouchers.id", nullable=False, ondelete="CASCADE")
    kind: Mapped[str] = string(10, nullable=False)  # IRN | EWAY
    status: Mapped[str] = string(20, nullable=False)  # GENERATED | CANCELLED | FAILED
    irn: Mapped[str | None] = string(64)
    ack_no: Mapped[str | None] = string(30)
    ack_date: Mapped[datetime | None] = ts()
    signed_qr: Mapped[str | None] = textcol()
    eway_bill_no: Mapped[str | None] = string(20)
    valid_until: Mapped[datetime | None] = ts()
    raw: Mapped[Any] = jsonb()
    created_at: Mapped[datetime] = ts_now()
