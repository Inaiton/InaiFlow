"""Accounts DTOs — names and fields exactly as in ``docs/api/contract.api`` (accounts sections, not payroll/taxation)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from app.core.money import DecimalStr
from app.core.schemas import InModel, OutModel

Nature = Literal["ASSETS", "LIABILITIES", "INCOME", "EXPENSES"]
DrCr = Literal["DR", "CR"]
VoucherStatus = Literal["REGULAR", "OPTIONAL", "MEMORANDUM", "POST_DATED", "CANCELLED"]
BillRefType = Literal["NEW_REF", "AGAINST_REF", "ADVANCE", "ON_ACCOUNT"]
Movement = Literal["INWARD", "OUTWARD"]
ValuationMethod = Literal["WEIGHTED_AVG", "FIFO", "LIFO", "STANDARD"]


# ---------------------------------------------------------------- masters
class GroupOut(OutModel):
    id: uuid.UUID
    name: str
    parent_group_id: uuid.UUID | None
    nature: Nature
    affects_gross_profit: bool
    is_system_group: bool
    system_code: str | None


class GroupIn(InModel):
    name: str = Field(min_length=1, max_length=150)
    parent_group_id: uuid.UUID


class GroupUpdateIn(InModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    parent_group_id: uuid.UUID | None = None


class PartyDetails(InModel):
    gstin: str | None = None
    state_code: str | None = None
    pan: str | None = None
    msme_type: str | None = None
    udyam_no: str | None = None
    bank_account: str | None = None
    ifsc: str | None = None
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    is_sez: bool = False
    is_unregistered: bool = False
    deductee_type: str | None = None


class TaxConfig(InModel):
    tax_type: str
    gst_head: str | None = None
    rate: DecimalStr | None = None
    tds_section: str | None = None


class InterestConfig(InModel):
    rate_pct: DecimalStr
    basis: str
    grace_days: int = 0


class LedgerOut(OutModel):
    id: uuid.UUID
    group_id: uuid.UUID
    group_name: str
    nature: Nature
    name: str
    alias: str | None
    system_code: str | None
    currency_code: str
    opening_balance: DecimalStr
    opening_balance_type: DrCr
    maintain_bill_by_bill: bool
    default_credit_days: int | None
    credit_limit: DecimalStr | None
    party_details: dict[str, Any] | None
    tax_config: dict[str, Any] | None
    interest_config: dict[str, Any] | None
    is_active: bool
    closing_balance: DecimalStr
    closing_balance_type: DrCr
    created_at: datetime


class LedgerIn(InModel):
    group_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    alias: str | None = Field(default=None, max_length=100)
    currency_code: str | None = None
    opening_balance: DecimalStr = Field(default=0, ge=0)
    opening_balance_type: DrCr = "DR"
    maintain_bill_by_bill: bool = False
    default_credit_days: int | None = Field(default=None, ge=0, le=3650)
    credit_limit: DecimalStr | None = Field(default=None, ge=0)
    party_details: PartyDetails | None = None
    tax_config: TaxConfig | None = None
    interest_config: InterestConfig | None = None
    is_active: bool = True


class LedgerStatementLine(OutModel):
    date: date
    voucher_id: uuid.UUID
    voucher_number: str
    voucher_type: str
    particulars: str
    narration: str | None
    debit: DecimalStr
    credit: DecimalStr
    running_balance: DecimalStr
    running_type: DrCr


class LedgerStatementOut(OutModel):
    ledger: LedgerOut
    date_from: date
    date_to: date
    opening_balance: DecimalStr
    opening_type: DrCr
    lines: list[LedgerStatementLine]
    total_debit: DecimalStr
    total_credit: DecimalStr
    closing_balance: DecimalStr
    closing_type: DrCr


class OutstandingBillOut(OutModel):
    ref_name: str
    bill_date: date
    due_date: date | None
    amount: DecimalStr
    pending: DecimalStr
    pending_type: DrCr
    overdue_days: int


class CostCentreOut(OutModel):
    id: uuid.UUID
    category_name: str
    name: str
    parent_id: uuid.UUID | None
    linked_period_run_id: uuid.UUID | None
    budget_amount: DecimalStr | None
    actual_amount: DecimalStr


class CostCentreIn(InModel):
    category_name: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None
    budget_amount: DecimalStr | None = None


class VoucherTypeOut(OutModel):
    id: uuid.UUID
    name: str
    base_type: str
    is_accounting: bool
    is_system: bool
    shortcut: str | None
    numbering_method: str
    prefix: str
    suffix: str
    zero_padding: int
    next_number: int


class VoucherTypeIn(InModel):
    name: str = Field(min_length=1, max_length=100)
    base_type: str
    numbering_method: str = "AUTOMATIC"
    prefix: str = Field(default="", max_length=30)
    suffix: str = Field(default="", max_length=30)
    zero_padding: int = Field(default=4, ge=0, le=10)
    next_number: int = Field(default=1, ge=1)


class VoucherTypeUpdateIn(InModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    numbering_method: str | None = None
    prefix: str | None = Field(default=None, max_length=30)
    suffix: str | None = Field(default=None, max_length=30)
    zero_padding: int | None = Field(default=None, ge=0, le=10)
    next_number: int | None = Field(default=None, ge=1)


class CurrencyOut(OutModel):
    id: uuid.UUID
    code: str
    symbol: str
    name: str
    decimal_places: int
    latest_rate: DecimalStr | None
    latest_rate_date: date | None


class CurrencyIn(InModel):
    code: str = Field(min_length=3, max_length=10)
    symbol: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=100)
    decimal_places: int = Field(default=2, ge=0, le=4)


class ExchangeRateIn(InModel):
    rate_date: date
    rate_to_base: DecimalStr = Field(gt=0)


class GodownOut(OutModel):
    id: uuid.UUID
    name: str
    parent_godown_id: uuid.UUID | None
    godown_type: str
    is_system: bool


class GodownIn(InModel):
    name: str = Field(min_length=1, max_length=150)
    parent_godown_id: uuid.UUID | None = None
    godown_type: str = "INTERNAL"


class StockGroupOut(OutModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None


class StockGroupIn(InModel):
    name: str = Field(min_length=1, max_length=150)
    parent_id: uuid.UUID | None = None


class BomComponent(InModel):
    raw_item_id: uuid.UUID
    qty_per_unit: DecimalStr = Field(gt=0)
    scrap_pct: DecimalStr = Field(default=0, ge=0, lt=100)


class StockItemOut(OutModel):
    id: uuid.UUID
    target_type: str
    name: str
    sku_code: str | None
    stock_group_id: uuid.UUID | None
    stock_group_name: str | None
    uom_primary: str
    uom_alternate: str | None
    uom_conversion_factor: DecimalStr | None
    valuation_method: str
    hsn_sac_code: str | None
    gst_rate: DecimalStr
    opening_qty: DecimalStr
    opening_rate: DecimalStr
    reorder_level: DecimalStr | None
    diagram_url: str | None
    custom_fields: Any
    bom_components: list[dict[str, Any]]
    closing_qty: DecimalStr
    closing_value: DecimalStr
    created_at: datetime


class StockItemIn(InModel):
    target_type: str = "STOCK_ITEM"
    name: str = Field(min_length=1, max_length=200)
    sku_code: str | None = Field(default=None, max_length=100)
    stock_group_id: uuid.UUID | None = None
    uom_primary: str = Field(default="Nos", max_length=30)
    uom_alternate: str | None = Field(default=None, max_length=30)
    uom_conversion_factor: DecimalStr | None = None
    valuation_method: ValuationMethod = "WEIGHTED_AVG"
    hsn_sac_code: str | None = Field(default=None, max_length=20)
    gst_rate: DecimalStr = Field(default=18, ge=0, le=100)
    opening_qty: DecimalStr = 0
    opening_rate: DecimalStr = Field(default=0, ge=0)
    reorder_level: DecimalStr | None = None
    diagram_storage_key: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    bom_components: list[BomComponent] = Field(default_factory=list)


class StockItemUploadIn(InModel):
    content_type: str
    size_bytes: int = Field(gt=0)
    file_name: str = Field(min_length=1, max_length=255)


class AccountsSettings(InModel):
    books_locked_until: date | None = None
    invoice_show_logo: bool = True
    invoice_terms: str | None = None
    invoice_declaration: str | None = None
    invoice_bank_details: str | None = None
    invoice_footer: str | None = None
    default_sales_voucher_type_id: uuid.UUID | None = None
    default_purchase_voucher_type_id: uuid.UUID | None = None


# ---------------------------------------------------------------- vouchers & inventory
class BillAllocation(InModel):
    ref_type: BillRefType
    ref_name: str = Field(min_length=1, max_length=100)
    amount: DecimalStr = Field(gt=0)
    due_date: date | None = None


class EntryIn(InModel):
    ledger_id: uuid.UUID
    entry_type: DrCr
    amount: DecimalStr = Field(gt=0)
    cost_centre_id: uuid.UUID | None = None
    bill_allocations: list[BillAllocation] = Field(default_factory=list)
    instrument_no: str | None = Field(default=None, max_length=50)
    instrument_date: date | None = None


class InventoryIn(InModel):
    stock_item_id: uuid.UUID
    godown_id: uuid.UUID
    movement_type: Movement
    quantity: DecimalStr = Field(gt=0)
    rate: DecimalStr = Field(ge=0)
    amount: DecimalStr | None = Field(default=None, ge=0)
    batch_number: str | None = Field(default=None, max_length=100)
    gst_rate: DecimalStr | None = None


class GstIn(InModel):
    place_of_supply_state_code: str | None = None
    reverse_charge: bool = False
    is_export: bool = False
    is_sez: bool = False


class VoucherIn(InModel):
    voucher_type_id: uuid.UUID
    voucher_date: date
    party_ledger_id: uuid.UUID | None = None
    supplier_invoice_no: str | None = Field(default=None, max_length=100)
    supplier_invoice_date: date | None = None
    status: VoucherStatus = "REGULAR"
    narration: str | None = Field(default=None, max_length=4000)
    entries: list[EntryIn] = Field(default_factory=list, max_length=500)
    inventory: list[InventoryIn] = Field(default_factory=list, max_length=500)
    gst: GstIn | None = None
    linked_period_run_id: uuid.UUID | None = None
    linked_step_id: uuid.UUID | None = None
    attachment_document_ids: list[uuid.UUID] = Field(default_factory=list)
    edit_reason: str | None = Field(default=None, max_length=1000)


class EntryOut(OutModel):
    id: uuid.UUID
    ledger_id: uuid.UUID
    ledger_name: str
    entry_type: DrCr
    amount: DecimalStr
    cost_centre_id: uuid.UUID | None
    cost_centre_name: str | None
    bill_allocations: list[dict[str, Any]]
    instrument_no: str | None
    instrument_date: date | None
    bank_reconciliation_date: date | None


class InventoryOut(OutModel):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    stock_item_name: str
    uom: str
    godown_id: uuid.UUID
    godown_name: str
    movement_type: str
    quantity: DecimalStr
    rate: DecimalStr
    amount: DecimalStr
    batch_number: str | None
    gst_rate: DecimalStr | None


class DocumentRef(OutModel):
    id: uuid.UUID
    title: str
    file_mime_type: str | None


class VoucherSummary(OutModel):
    id: uuid.UUID
    voucher_number: str
    voucher_date: date
    voucher_type_id: uuid.UUID
    voucher_type_name: str
    base_type: str
    party_ledger_id: uuid.UUID | None
    party_name: str | None
    total_amount: DecimalStr
    status: VoucherStatus
    narration: str | None
    linked_period_run_id: uuid.UUID | None
    created_at: datetime


class VoucherOut(VoucherSummary):
    supplier_invoice_no: str | None
    supplier_invoice_date: date | None
    gst_metadata: Any | None
    linked_step_id: uuid.UUID | None
    entries: list[EntryOut]
    inventory: list[InventoryOut]
    attachments: list[DocumentRef]
    created_by_name: str
    approved_by_name: str | None
    cancel_reason: str | None
    updated_at: datetime


class CancelIn(InModel):
    reason: str = Field(min_length=3, max_length=1000)


class AttachDocumentIn(InModel):
    document_id: uuid.UUID


class TaxLineIn(InModel):
    ledger_id: uuid.UUID
    stock_item_id: uuid.UUID | None = None
    quantity: DecimalStr | None = None
    rate: DecimalStr | None = None
    amount: DecimalStr = Field(ge=0)
    gst_rate: DecimalStr | None = None
    hsn_sac_code: str | None = None


class ComputeTaxIn(InModel):
    voucher_type_id: uuid.UUID
    voucher_date: date
    party_ledger_id: uuid.UUID
    lines: list[TaxLineIn] = Field(min_length=1, max_length=500)
    gst: GstIn | None = None


class TaxBreakup(OutModel):
    hsn_sac_code: str | None
    gst_rate: DecimalStr
    taxable: DecimalStr
    cgst: DecimalStr
    sgst: DecimalStr
    igst: DecimalStr
    cess: DecimalStr


class ComputeTaxOut(OutModel):
    tax_split: str
    taxable_total: DecimalStr
    cgst: DecimalStr
    sgst: DecimalStr
    igst: DecimalStr
    cess: DecimalStr
    round_off: DecimalStr
    invoice_total: DecimalStr
    breakup: list[TaxBreakup]
    suggested_entries: list[EntryIn]
    warnings: list[str]


class StockSummaryRow(OutModel):
    stock_item_id: uuid.UUID
    name: str
    stock_group_name: str | None
    uom: str
    valuation_method: str
    quantity: DecimalStr
    rate: DecimalStr
    value: DecimalStr
    reorder_level: DecimalStr | None
    below_reorder: bool


class StockMovementOut(OutModel):
    date: date
    voucher_id: uuid.UUID
    voucher_number: str
    voucher_type: str
    godown_name: str
    inward_qty: DecimalStr
    outward_qty: DecimalStr
    rate: DecimalStr
    balance_qty: DecimalStr
    balance_value: DecimalStr


# ---------------------------------------------------------------- banking
class BankAccountOut(OutModel):
    ledger_id: uuid.UUID
    name: str
    bank_account: str | None
    ifsc: str | None
    book_balance: DecimalStr
    book_balance_type: DrCr
    unreconciled_count: int
    last_reconciled_on: date | None


class ReconEntryOut(OutModel):
    entry_id: uuid.UUID
    voucher_id: uuid.UUID
    voucher_number: str
    voucher_type: str
    voucher_date: date
    particulars: str
    debit: DecimalStr
    credit: DecimalStr
    instrument_no: str | None
    instrument_date: date | None
    bank_reconciliation_date: date | None


class StatementLineOut(OutModel):
    id: uuid.UUID
    txn_date: date
    value_date: date | None
    description: str
    reference: str | None
    debit: DecimalStr
    credit: DecimalStr
    balance: DecimalStr | None
    status: str
    matched_entry_id: uuid.UUID | None


class ReconciliationOut(OutModel):
    ledger_id: uuid.UUID
    as_of: date
    balance_as_per_books: DecimalStr
    books_type: DrCr
    amounts_not_reflected_in_bank: DecimalStr
    balance_as_per_bank: DecimalStr
    entries: list[ReconEntryOut]
    statement_lines: list[StatementLineOut]


class ReconcileIn(InModel):
    bank_reconciliation_date: date | None


class StatementImportOut(OutModel):
    import_id: uuid.UUID
    format: str
    lines_imported: int
    auto_matched: int
    duplicates_skipped: int


class MatchIn(InModel):
    entry_id: uuid.UUID


class ChequeBookIn(InModel):
    bank_ledger_id: uuid.UUID
    from_number: str = Field(pattern=r"^\d{1,20}$")
    to_number: str = Field(pattern=r"^\d{1,20}$")


class ChequeBookOut(OutModel):
    id: uuid.UUID
    bank_ledger_id: uuid.UUID
    bank_name: str
    from_number: str
    to_number: str
    next_number: str
    used_count: int
    created_at: datetime


class ChequeOut(OutModel):
    entry_id: uuid.UUID
    voucher_id: uuid.UUID
    voucher_number: str
    voucher_date: date
    instrument_no: str
    instrument_date: date | None
    payee: str
    amount: DecimalStr
    bank_ledger_id: uuid.UUID
    status: str


# ---------------------------------------------------------------- reports & dashboard
class TrialBalanceRow(OutModel):
    kind: str
    id: uuid.UUID
    name: str
    level: int
    parent_id: uuid.UUID | None
    opening_dr: DecimalStr
    opening_cr: DecimalStr
    debit: DecimalStr
    credit: DecimalStr
    closing_dr: DecimalStr
    closing_cr: DecimalStr


class TrialBalanceOut(OutModel):
    date_from: date
    date_to: date
    rows: list[TrialBalanceRow]
    total_debit: DecimalStr
    total_credit: DecimalStr
    difference: DecimalStr


class StatementSection(OutModel):
    label: str
    amount: DecimalStr
    group_id: uuid.UUID | None = None
    children: list[StatementSection] = Field(default_factory=list)


class ProfitLossOut(OutModel):
    date_from: date
    date_to: date
    trading_debit: list[StatementSection]
    trading_credit: list[StatementSection]
    gross_profit: DecimalStr
    pnl_debit: list[StatementSection]
    pnl_credit: list[StatementSection]
    net_profit: DecimalStr
    closing_stock: DecimalStr
    opening_stock: DecimalStr


class BalanceSheetOut(OutModel):
    as_of: date
    equity_and_liabilities: list[StatementSection]
    assets: list[StatementSection]
    total_liabilities: DecimalStr
    total_assets: DecimalStr
    difference: DecimalStr


class CashFlowOut(OutModel):
    date_from: date
    date_to: date
    operating: list[StatementSection]
    investing: list[StatementSection]
    financing: list[StatementSection]
    net_change: DecimalStr
    opening_cash: DecimalStr
    closing_cash: DecimalStr


class RatioOut(OutModel):
    key: str
    label: str
    value: DecimalStr | None
    formula: str


class AgeingRow(OutModel):
    ledger_id: uuid.UUID
    party_name: str
    total: DecimalStr
    buckets: dict[str, DecimalStr]
    msme_overdue: bool


class AgeingOut(OutModel):
    kind: str
    as_of: date
    bucket_labels: list[str]
    rows: list[AgeingRow]
    totals: dict[str, DecimalStr]


class BatchCostRow(OutModel):
    period_run_id: uuid.UUID
    run_title: str
    period_month: date
    stock_item_name: str | None
    accepted_qty: DecimalStr
    rejected_qty: DecimalStr
    total_debit: DecimalStr
    total_credit: DecimalStr
    net_cost: DecimalStr
    unit_cost: DecimalStr
    status: str


class KpiOut(OutModel):
    key: str
    label: str
    value: DecimalStr
    change_pct: DecimalStr | None


class CashFlowPoint(OutModel):
    month: str
    inflow: DecimalStr
    outflow: DecimalStr


class AlertOut(OutModel):
    severity: str
    kind: str
    message: str
    link: str | None


class AccountsDashboardOut(OutModel):
    kpis: list[KpiOut]
    cash_flow: list[CashFlowPoint]
    alerts: list[AlertOut]
    recent_vouchers: list[VoucherSummary]


class ExceptionOut(OutModel):
    kind: str
    severity: str
    message: str
    entity_type: str
    entity_id: uuid.UUID | None
    link: str | None
