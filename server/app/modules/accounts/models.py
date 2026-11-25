"""Accounts tables: masters, vouchers (double entry), inventory, currencies, banking."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Date, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.orm import (
    MONEY,
    RATE,
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


class AccountGroup(Base):
    __tablename__ = "account_groups"
    __table_args__ = (UniqueConstraint("org_id", "name"), UniqueConstraint("org_id", "system_code"))

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = string(150, nullable=False)
    parent_group_id: Mapped[uuid.UUID | None] = fk("account_groups.id")
    nature: Mapped[str] = string(30, nullable=False)  # ASSETS | LIABILITIES | INCOME | EXPENSES
    affects_gross_profit: Mapped[bool] = flag(False)
    is_system_group: Mapped[bool] = flag(False)
    system_code: Mapped[str | None] = string(50)


class Ledger(Base):
    __tablename__ = "ledgers"
    __table_args__ = (UniqueConstraint("org_id", "name"), UniqueConstraint("org_id", "system_code"))

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    group_id: Mapped[uuid.UUID] = fk("account_groups.id", nullable=False)
    name: Mapped[str] = string(200, nullable=False)
    alias: Mapped[str | None] = string(100)
    system_code: Mapped[str | None] = string(50)
    currency_code: Mapped[str] = string(10, nullable=False, default="INR")
    opening_balance: Mapped[Decimal] = money()
    opening_balance_type: Mapped[str] = string(2, nullable=False, default="DR")
    maintain_bill_by_bill: Mapped[bool] = flag(False)
    default_credit_days: Mapped[int | None] = integer(nullable=True, default=0)
    credit_limit: Mapped[Decimal | None] = money(nullable=True, default=None)
    party_details: Mapped[Any] = jsonb()
    tax_config: Mapped[Any] = jsonb()
    interest_config: Mapped[Any] = jsonb()
    is_active: Mapped[bool] = flag(True)
    created_at: Mapped[datetime] = ts_now()


class CostCentre(Base):
    __tablename__ = "cost_centres"
    __table_args__ = (UniqueConstraint("org_id", "name"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    category_name: Mapped[str] = string(100, nullable=False, default="Primary Cost Category")
    name: Mapped[str] = string(200, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = fk("cost_centres.id")
    linked_period_run_id: Mapped[uuid.UUID | None] = uuid_col(index=True)
    budget_amount: Mapped[Decimal | None] = money(nullable=True, default=None)


class VoucherType(Base):
    __tablename__ = "voucher_types"
    __table_args__ = (UniqueConstraint("org_id", "name"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = string(100, nullable=False)
    base_type: Mapped[str] = string(50, nullable=False)
    is_accounting: Mapped[bool] = flag(True)
    is_system: Mapped[bool] = flag(False)
    shortcut: Mapped[str | None] = string(20)
    numbering_method: Mapped[str] = string(30, nullable=False, default="AUTOMATIC")
    prefix: Mapped[str | None] = string(30, default="")
    suffix: Mapped[str | None] = string(30, default="")
    zero_padding: Mapped[int] = integer(default=4)
    next_number: Mapped[int] = integer(default=1)


class Voucher(Base):
    __tablename__ = "vouchers"
    __table_args__ = (
        UniqueConstraint("org_id", "voucher_type_id", "voucher_number"),
        Index("ix_vouchers_org_id_voucher_date", "org_id", "voucher_date"),
    )

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    voucher_type_id: Mapped[uuid.UUID] = fk("voucher_types.id", nullable=False)
    voucher_number: Mapped[str] = string(100, nullable=False)
    voucher_date: Mapped[date] = mapped_column(Date, nullable=False)
    party_ledger_id: Mapped[uuid.UUID | None] = fk("ledgers.id")
    supplier_invoice_no: Mapped[str | None] = string(100)
    supplier_invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = string(30, nullable=False, default="REGULAR")
    total_amount: Mapped[Decimal] = money(default=None)
    narration: Mapped[str | None] = textcol()
    gst_metadata: Mapped[Any] = jsonb()
    linked_period_run_id: Mapped[uuid.UUID | None] = uuid_col(index=True)
    linked_step_id: Mapped[uuid.UUID | None] = uuid_col(index=True)
    created_by: Mapped[uuid.UUID] = fk("users.id", nullable=False)
    approved_by: Mapped[uuid.UUID | None] = fk("users.id")
    cancel_reason: Mapped[str | None] = textcol()
    cancelled_at: Mapped[datetime | None] = ts()
    idempotency_key: Mapped[str | None] = string(255)
    created_at: Mapped[datetime] = ts_now()
    updated_at: Mapped[datetime] = ts_now()


class VoucherEntry(Base):
    __tablename__ = "voucher_entries"
    __table_args__ = (
        CheckConstraint("entry_type IN ('DR', 'CR')", name="entry_type"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
    )

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    voucher_id: Mapped[uuid.UUID] = fk("vouchers.id", nullable=False, ondelete="CASCADE")
    ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    entry_type: Mapped[str] = string(2, nullable=False)
    amount: Mapped[Decimal] = money(default=None)
    cost_centre_id: Mapped[uuid.UUID | None] = fk("cost_centres.id")
    bill_allocations: Mapped[Any] = jsonb()
    bank_reconciliation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    instrument_no: Mapped[str | None] = string(50)
    instrument_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Godown(Base):
    __tablename__ = "godowns"
    __table_args__ = (UniqueConstraint("org_id", "name"), UniqueConstraint("org_id", "system_code"))

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = string(150, nullable=False)
    parent_godown_id: Mapped[uuid.UUID | None] = fk("godowns.id")
    godown_type: Mapped[str] = string(50, nullable=False, default="INTERNAL")  # INTERNAL|WIP|SCRAP|JOB_WORKER|FG
    is_system: Mapped[bool] = flag(False)
    system_code: Mapped[str | None] = string(20)  # MAIN | WIP | SCRAP | FG


class StockGroup(Base):
    __tablename__ = "stock_groups"
    __table_args__ = (UniqueConstraint("org_id", "name"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = string(150, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = fk("stock_groups.id")


class StockItem(Base):
    __tablename__ = "stock_items"
    __table_args__ = (UniqueConstraint("org_id", "name"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    target_type: Mapped[str] = string(30, nullable=False, default="STOCK_ITEM")
    name: Mapped[str] = string(200, nullable=False)
    sku_code: Mapped[str | None] = string(100)
    stock_group_id: Mapped[uuid.UUID | None] = fk("stock_groups.id")
    uom_primary: Mapped[str] = string(30, nullable=False, default="Nos")
    uom_alternate: Mapped[str | None] = string(30)
    uom_conversion_factor: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    valuation_method: Mapped[str] = string(30, nullable=False, default="WEIGHTED_AVG")
    hsn_sac_code: Mapped[str | None] = string(20)
    gst_rate: Mapped[Decimal] = mapped_column(RATE, nullable=False, server_default="18")
    opening_qty: Mapped[Decimal] = money()
    opening_rate: Mapped[Decimal] = money()
    reorder_level: Mapped[Decimal | None] = money(nullable=True)
    engineering_diagram_url: Mapped[str | None] = textcol()
    diagram_storage_key: Mapped[str | None] = textcol()
    custom_fields: Mapped[Any] = jsonb(nullable=False, default="{}")
    bom_components: Mapped[Any] = jsonb()
    created_at: Mapped[datetime] = ts_now()


class VoucherInventoryEntry(Base):
    __tablename__ = "voucher_inventory_entries"
    __table_args__ = (
        CheckConstraint("movement_type IN ('INWARD', 'OUTWARD')", name="movement_type"),
        Index("ix_voucher_inventory_entries_org_id_stock_item_id", "org_id", "stock_item_id"),
    )

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    voucher_id: Mapped[uuid.UUID] = fk("vouchers.id", nullable=False, ondelete="CASCADE")
    stock_item_id: Mapped[uuid.UUID] = fk("stock_items.id", nullable=False)
    godown_id: Mapped[uuid.UUID] = fk("godowns.id", nullable=False)
    movement_type: Mapped[str] = string(10, nullable=False)
    batch_number: Mapped[str | None] = string(100)
    quantity: Mapped[Decimal] = money(default=None)
    rate: Mapped[Decimal] = money(default=None)
    amount: Mapped[Decimal] = money(default=None)
    gst_rate: Mapped[Decimal | None] = mapped_column(RATE, nullable=True, server_default="0")


class Currency(Base):
    __tablename__ = "currencies"
    __table_args__ = (UniqueConstraint("org_id", "code"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    code: Mapped[str] = string(10, nullable=False)
    symbol: Mapped[str] = string(10, nullable=False)
    name: Mapped[str] = string(100, nullable=False)
    decimal_places: Mapped[int] = integer(default=2)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (UniqueConstraint("org_id", "currency_code", "rate_date"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    currency_code: Mapped[str] = string(10, nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate_to_base: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class ChequeBook(Base):
    __tablename__ = "cheque_books"

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    bank_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    from_number: Mapped[str] = string(20, nullable=False)
    to_number: Mapped[str] = string(20, nullable=False)
    next_number: Mapped[str] = string(20, nullable=False)
    created_at: Mapped[datetime] = ts_now()


class BankStatementImport(Base):
    __tablename__ = "bank_statement_imports"

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    bank_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    file_name: Mapped[str] = string(255, nullable=False)
    format: Mapped[str] = string(10, nullable=False)  # CSV | OFX | MT940
    imported_by: Mapped[uuid.UUID | None] = fk("users.id")
    line_count: Mapped[int] = integer(default=0)
    created_at: Mapped[datetime] = ts_now()


class BankStatementLine(Base):
    __tablename__ = "bank_statement_lines"
    __table_args__ = (Index("ix_bank_statement_lines_dedupe", "org_id", "bank_ledger_id", "dedupe_hash"),)

    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    import_id: Mapped[uuid.UUID] = fk("bank_statement_imports.id", nullable=False, ondelete="CASCADE")
    bank_ledger_id: Mapped[uuid.UUID] = fk("ledgers.id", nullable=False)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = textcol(nullable=False)
    reference: Mapped[str | None] = string(100)
    debit: Mapped[Decimal] = money()
    credit: Mapped[Decimal] = money()
    balance: Mapped[Decimal | None] = money(nullable=True, default=None)
    matched_entry_id: Mapped[uuid.UUID | None] = fk("voucher_entries.id", ondelete="SET NULL")
    status: Mapped[str] = string(20, nullable=False, default="UNMATCHED")  # UNMATCHED|MATCHED|IGNORED
    dedupe_hash: Mapped[str | None] = string(64)
