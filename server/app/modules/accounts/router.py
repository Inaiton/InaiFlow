"""Accounts routes (contract sections: masters, vouchers & inventory, banking, reports & dashboard). Thin handlers."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.core.context import TenantContext
from app.core.deps import TenantDB, require
from app.core.idempotency import Idem
from app.core.pagination import Page, Paging
from app.core.schemas import AuditLogOut, UploadTicket
from app.modules.accounts import banking_service as banking
from app.modules.accounts import inventory_service as inventory
from app.modules.accounts import report_service as reports
from app.modules.accounts import service, tally_xml
from app.modules.accounts import voucher_service as vouchers
from app.modules.accounts.schemas import (
    AccountsDashboardOut,
    AccountsSettings,
    AgeingOut,
    AttachDocumentIn,
    BalanceSheetOut,
    BankAccountOut,
    BatchCostRow,
    CancelIn,
    CashFlowOut,
    ChequeBookIn,
    ChequeBookOut,
    ChequeOut,
    ComputeTaxIn,
    ComputeTaxOut,
    CostCentreIn,
    CostCentreOut,
    CurrencyIn,
    CurrencyOut,
    ExceptionOut,
    ExchangeRateIn,
    GodownIn,
    GodownOut,
    GroupIn,
    GroupOut,
    GroupUpdateIn,
    LedgerIn,
    LedgerOut,
    LedgerStatementOut,
    MatchIn,
    Nature,
    OutstandingBillOut,
    ProfitLossOut,
    RatioOut,
    ReconcileIn,
    ReconciliationOut,
    ReconEntryOut,
    StatementImportOut,
    StatementLineOut,
    StockGroupIn,
    StockGroupOut,
    StockItemIn,
    StockItemOut,
    StockItemUploadIn,
    StockMovementOut,
    StockSummaryRow,
    TrialBalanceOut,
    VoucherIn,
    VoucherOut,
    VoucherStatus,
    VoucherSummary,
    VoucherTypeIn,
    VoucherTypeOut,
    VoucherTypeUpdateIn,
)

router = APIRouter(tags=["accounts"])
NO_CONTENT = status.HTTP_204_NO_CONTENT
CREATED = status.HTTP_201_CREATED


def G(key: str, level: str, acl: str | None = None) -> type[TenantContext]:  # noqa: N802 - dependency alias factory
    return Annotated[TenantContext, Depends(require(f"accounts.{key}", level, acl_resource=acl))]  # type: ignore[return-value]


LgR, LgW, LgF = G("ledgers_groups", "READ"), G("ledgers_groups", "WRITE"), G("ledgers_groups", "FULL")
VR, VW, VF = G("vouchers", "READ"), G("vouchers", "WRITE"), G("vouchers", "FULL")
InvR, InvW, InvF = G("inventory_masters", "READ"), G("inventory_masters", "WRITE"), G("inventory_masters", "FULL")
ItemR = G("inventory_masters", "READ", "STOCK_ITEM")
ItemW = G("inventory_masters", "WRITE", "STOCK_ITEM")
ItemF = G("inventory_masters", "FULL", "STOCK_ITEM")
BkR, BkW = G("banking", "READ"), G("banking", "WRITE")
RpR, RpF = G("reports", "READ"), G("reports", "FULL")
DashR = G("dashboard", "READ")


def _file(data: bytes, mime: str, name: str) -> Response:
    return Response(content=data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ================================================================= groups
@router.get("/accounts/groups", response_model=list[GroupOut])
async def list_groups(ctx: LgR, db: TenantDB) -> list[GroupOut]:
    return await service.list_groups(db, ctx)


@router.post("/accounts/groups", response_model=GroupOut, status_code=CREATED)
async def create_group(body: GroupIn, ctx: LgW, db: TenantDB, idem: Idem) -> GroupOut:
    return await idem.save(await service.create_group(db, ctx, body), 201)


@router.patch("/accounts/groups/{group_id}", response_model=GroupOut)
async def update_group(group_id: uuid.UUID, body: GroupUpdateIn, ctx: LgW, db: TenantDB) -> GroupOut:
    return await service.update_group(db, ctx, group_id, body)


@router.delete("/accounts/groups/{group_id}", status_code=NO_CONTENT)
async def delete_group(group_id: uuid.UUID, ctx: LgF, db: TenantDB) -> Response:
    await service.delete_group(db, ctx, group_id)
    return Response(status_code=NO_CONTENT)


# ================================================================= ledgers
@router.get("/accounts/ledgers", response_model=Page[LedgerOut])
async def list_ledgers(ctx: LgR, db: TenantDB, page: Paging, q: str | None = None, group_id: uuid.UUID | None = None,
                       nature: Nature | None = None, party_only: bool = False, bank_only: bool = False,
                       include_inactive: bool = False) -> Page[LedgerOut]:  # fmt: skip
    return await service.list_ledgers(db, ctx, page, q=q, group_id=group_id, nature=nature, party_only=party_only,
                                      bank_only=bank_only, include_inactive=include_inactive)  # fmt: skip


@router.post("/accounts/ledgers", response_model=LedgerOut, status_code=CREATED)
async def create_ledger(body: LedgerIn, ctx: LgW, db: TenantDB, idem: Idem) -> LedgerOut:
    return await idem.save(await service.create_ledger(db, ctx, body), 201)


@router.get("/accounts/ledgers/{ledger_id}", response_model=LedgerOut)
async def get_ledger(ledger_id: uuid.UUID, ctx: LgR, db: TenantDB) -> LedgerOut:
    return await service.get_ledger(db, ctx, ledger_id)


@router.patch("/accounts/ledgers/{ledger_id}", response_model=LedgerOut)
async def update_ledger(ledger_id: uuid.UUID, body: LedgerIn, ctx: LgW, db: TenantDB) -> LedgerOut:
    return await service.update_ledger(db, ctx, ledger_id, body)


@router.delete("/accounts/ledgers/{ledger_id}", status_code=NO_CONTENT)
async def delete_ledger(ledger_id: uuid.UUID, ctx: LgF, db: TenantDB) -> Response:
    await service.delete_ledger(db, ctx, ledger_id)
    return Response(status_code=NO_CONTENT)


@router.get("/accounts/ledgers/{ledger_id}/statement", response_model=LedgerStatementOut)
async def ledger_statement(ledger_id: uuid.UUID, ctx: RpR, db: TenantDB, date_from: date = Query(),
                           date_to: date = Query()) -> LedgerStatementOut:  # fmt: skip
    return await service.ledger_statement(db, ctx, ledger_id, date_from, date_to)


@router.get("/accounts/ledgers/{ledger_id}/bills", response_model=list[OutstandingBillOut])
async def ledger_bills(
    ledger_id: uuid.UUID, ctx: VR, db: TenantDB, as_of: date | None = None
) -> list[OutstandingBillOut]:
    return await service.ledger_bills(db, ctx, ledger_id, as_of)


# ================================================================= cost centres
@router.get("/accounts/cost-centres", response_model=list[CostCentreOut])
async def list_cost_centres(ctx: LgR, db: TenantDB) -> list[CostCentreOut]:
    return await service.list_cost_centres(db, ctx)


@router.post("/accounts/cost-centres", response_model=CostCentreOut, status_code=CREATED)
async def create_cost_centre(body: CostCentreIn, ctx: LgW, db: TenantDB, idem: Idem) -> CostCentreOut:
    return await idem.save(await service.create_cost_centre(db, ctx, body), 201)


@router.patch("/accounts/cost-centres/{cost_centre_id}", response_model=CostCentreOut)
async def update_cost_centre(cost_centre_id: uuid.UUID, body: CostCentreIn, ctx: LgW, db: TenantDB) -> CostCentreOut:
    return await service.update_cost_centre(db, ctx, cost_centre_id, body)


@router.delete("/accounts/cost-centres/{cost_centre_id}", status_code=NO_CONTENT)
async def delete_cost_centre(cost_centre_id: uuid.UUID, ctx: LgF, db: TenantDB) -> Response:
    await service.delete_cost_centre(db, ctx, cost_centre_id)
    return Response(status_code=NO_CONTENT)


# ================================================================= voucher types
@router.get("/accounts/voucher-types", response_model=list[VoucherTypeOut])
async def list_voucher_types(ctx: VR, db: TenantDB) -> list[VoucherTypeOut]:
    return await service.list_voucher_types(db, ctx)


@router.post("/accounts/voucher-types", response_model=VoucherTypeOut, status_code=CREATED)
async def create_voucher_type(body: VoucherTypeIn, ctx: VF, db: TenantDB, idem: Idem) -> VoucherTypeOut:
    return await idem.save(await service.create_voucher_type(db, ctx, body), 201)


@router.patch("/accounts/voucher-types/{voucher_type_id}", response_model=VoucherTypeOut)
async def update_voucher_type(voucher_type_id: uuid.UUID, body: VoucherTypeUpdateIn, ctx: VF, db: TenantDB
                              ) -> VoucherTypeOut:  # fmt: skip
    return await service.update_voucher_type(db, ctx, voucher_type_id, body)


# ================================================================= currencies
@router.get("/accounts/currencies", response_model=list[CurrencyOut])
async def list_currencies(ctx: LgR, db: TenantDB) -> list[CurrencyOut]:
    return await service.list_currencies(db, ctx)


@router.post("/accounts/currencies", response_model=CurrencyOut, status_code=CREATED)
async def create_currency(body: CurrencyIn, ctx: LgW, db: TenantDB, idem: Idem) -> CurrencyOut:
    return await idem.save(await service.create_currency(db, ctx, body), 201)


@router.post("/accounts/currencies/{currency_id}/rates", response_model=CurrencyOut)
async def add_rate(currency_id: uuid.UUID, body: ExchangeRateIn, ctx: LgW, db: TenantDB, idem: Idem) -> CurrencyOut:
    return await idem.save(await service.add_exchange_rate(db, ctx, currency_id, body))


# ================================================================= godowns / stock groups / items
@router.get("/accounts/godowns", response_model=list[GodownOut])
async def list_godowns(ctx: InvR, db: TenantDB) -> list[GodownOut]:
    return await service.list_godowns(db, ctx)


@router.post("/accounts/godowns", response_model=GodownOut, status_code=CREATED)
async def create_godown(body: GodownIn, ctx: InvW, db: TenantDB, idem: Idem) -> GodownOut:
    return await idem.save(await service.create_godown(db, ctx, body), 201)


@router.patch("/accounts/godowns/{godown_id}", response_model=GodownOut)
async def update_godown(godown_id: uuid.UUID, body: GodownIn, ctx: InvW, db: TenantDB) -> GodownOut:
    return await service.update_godown(db, ctx, godown_id, body)


@router.delete("/accounts/godowns/{godown_id}", status_code=NO_CONTENT)
async def delete_godown(godown_id: uuid.UUID, ctx: InvF, db: TenantDB) -> Response:
    await service.delete_godown(db, ctx, godown_id)
    return Response(status_code=NO_CONTENT)


@router.get("/accounts/stock-groups", response_model=list[StockGroupOut])
async def list_stock_groups(ctx: InvR, db: TenantDB) -> list[StockGroupOut]:
    return await service.list_stock_groups(db, ctx)


@router.post("/accounts/stock-groups", response_model=StockGroupOut, status_code=CREATED)
async def create_stock_group(body: StockGroupIn, ctx: InvW, db: TenantDB, idem: Idem) -> StockGroupOut:
    return await idem.save(await service.create_stock_group(db, ctx, body), 201)


@router.patch("/accounts/stock-groups/{stock_group_id}", response_model=StockGroupOut)
async def update_stock_group(stock_group_id: uuid.UUID, body: StockGroupIn, ctx: InvW, db: TenantDB) -> StockGroupOut:
    return await service.update_stock_group(db, ctx, stock_group_id, body)


@router.delete("/accounts/stock-groups/{stock_group_id}", status_code=NO_CONTENT)
async def delete_stock_group(stock_group_id: uuid.UUID, ctx: InvF, db: TenantDB) -> Response:
    await service.delete_stock_group(db, ctx, stock_group_id)
    return Response(status_code=NO_CONTENT)


@router.get("/accounts/stock-items", response_model=Page[StockItemOut])
async def list_stock_items(ctx: ItemR, db: TenantDB, page: Paging, q: str | None = None,
                           stock_group_id: uuid.UUID | None = None, target_type: str | None = None) -> Page[StockItemOut]:  # fmt: skip
    return await service.list_stock_items(db, ctx, page, q=q, stock_group_id=stock_group_id, target_type=target_type)


@router.post("/accounts/stock-items/upload-url", response_model=UploadTicket)
async def stock_item_upload_url(body: StockItemUploadIn, ctx: InvW) -> UploadTicket:
    return await service.stock_item_upload_url(ctx, body)


@router.post("/accounts/stock-items", response_model=StockItemOut, status_code=CREATED)
async def create_stock_item(body: StockItemIn, ctx: InvW, db: TenantDB, idem: Idem) -> StockItemOut:
    return await idem.save(await service.create_stock_item(db, ctx, body), 201)


@router.get("/accounts/stock-items/{item_id}", response_model=StockItemOut)
async def get_stock_item(item_id: uuid.UUID, ctx: ItemR, db: TenantDB) -> StockItemOut:
    return await service.get_stock_item(db, ctx, item_id)


@router.patch("/accounts/stock-items/{item_id}", response_model=StockItemOut)
async def update_stock_item(item_id: uuid.UUID, body: StockItemIn, ctx: ItemW, db: TenantDB) -> StockItemOut:
    return await service.update_stock_item(db, ctx, item_id, body)


@router.delete("/accounts/stock-items/{item_id}", status_code=NO_CONTENT)
async def delete_stock_item(item_id: uuid.UUID, ctx: ItemF, db: TenantDB) -> Response:
    await service.delete_stock_item(db, ctx, item_id)
    return Response(status_code=NO_CONTENT)


# ================================================================= settings
@router.get("/accounts/settings", response_model=AccountsSettings)
async def get_settings(ctx: VR, db: TenantDB) -> AccountsSettings:
    return await service.get_settings(db, ctx)


@router.put("/accounts/settings", response_model=AccountsSettings)
async def put_settings(body: AccountsSettings, ctx: VF, db: TenantDB) -> AccountsSettings:
    return await service.put_settings(db, ctx, body)


# ================================================================= vouchers
@router.get("/accounts/vouchers", response_model=Page[VoucherSummary])
async def list_vouchers(ctx: VR, db: TenantDB, page: Paging, date_from: date | None = None, date_to: date | None = None,
                        voucher_type_id: uuid.UUID | None = None, base_type: str | None = None,
                        party_ledger_id: uuid.UUID | None = None, ledger_id: uuid.UUID | None = None,
                        status: VoucherStatus | None = None, q: str | None = None,
                        linked_period_run_id: uuid.UUID | None = None) -> Page[VoucherSummary]:  # fmt: skip
    return await vouchers.list_vouchers(db, ctx, page, date_from=date_from, date_to=date_to,
                                        voucher_type_id=voucher_type_id, base_type=base_type,
                                        party_ledger_id=party_ledger_id, ledger_id=ledger_id, status=status, q=q,
                                        linked_period_run_id=linked_period_run_id)  # fmt: skip


@router.post("/accounts/vouchers/compute-tax", response_model=ComputeTaxOut)
async def compute_tax(body: ComputeTaxIn, ctx: VW, db: TenantDB) -> ComputeTaxOut:
    return await vouchers.compute_tax(db, ctx, body)


@router.post("/accounts/vouchers", response_model=VoucherOut, status_code=CREATED)
async def create_voucher(body: VoucherIn, ctx: VW, db: TenantDB, idem: Idem) -> VoucherOut:
    return await idem.save(await vouchers.create_voucher(db, ctx, body), 201)


@router.get("/accounts/vouchers/{voucher_id}", response_model=VoucherOut)
async def get_voucher(voucher_id: uuid.UUID, ctx: VR, db: TenantDB) -> VoucherOut:
    return await vouchers.get_voucher(db, ctx, voucher_id)


@router.put("/accounts/vouchers/{voucher_id}", response_model=VoucherOut)
async def update_voucher(voucher_id: uuid.UUID, body: VoucherIn, ctx: VW, db: TenantDB, idem: Idem) -> VoucherOut:
    return await idem.save(await vouchers.update_voucher(db, ctx, voucher_id, body))


@router.post("/accounts/vouchers/{voucher_id}/cancel", response_model=VoucherOut)
async def cancel_voucher(voucher_id: uuid.UUID, body: CancelIn, ctx: VF, db: TenantDB, idem: Idem) -> VoucherOut:
    return await idem.save(await vouchers.cancel_voucher(db, ctx, voucher_id, body.reason))


@router.get("/accounts/vouchers/{voucher_id}/edit-log", response_model=list[AuditLogOut])
async def edit_log(voucher_id: uuid.UUID, ctx: VR, db: TenantDB) -> list[AuditLogOut]:
    return await vouchers.edit_log(db, ctx, voucher_id)


@router.post("/accounts/vouchers/{voucher_id}/attachments", response_model=VoucherOut)
async def attach(voucher_id: uuid.UUID, body: AttachDocumentIn, ctx: VW, db: TenantDB) -> VoucherOut:
    return await vouchers.attach_document(db, ctx, voucher_id, body.document_id)


@router.get("/accounts/vouchers/{voucher_id}/print", response_class=Response)
async def print_voucher(voucher_id: uuid.UUID, ctx: VR, db: TenantDB, fmt: str | None = Query(None, alias="format")
                        ) -> Response:  # fmt: skip
    data, name = await vouchers.print_voucher(db, ctx, voucher_id, fmt)
    return _file(data, "application/pdf", name)


# ================================================================= inventory reports
@router.get("/accounts/inventory/stock-summary", response_model=list[StockSummaryRow])
async def stock_summary(ctx: InvR, db: TenantDB, as_of: date | None = None, godown_id: uuid.UUID | None = None,
                        stock_group_id: uuid.UUID | None = None) -> list[StockSummaryRow]:  # fmt: skip
    return await inventory.stock_summary(db, ctx, as_of=as_of, godown_id=godown_id, stock_group_id=stock_group_id)


@router.get("/accounts/inventory/items/{item_id}/movements", response_model=list[StockMovementOut])
async def item_movements(item_id: uuid.UUID, ctx: InvR, db: TenantDB, date_from: date = Query(), date_to: date = Query(),
                         godown_id: uuid.UUID | None = None) -> list[StockMovementOut]:  # fmt: skip
    return await inventory.item_movements(db, ctx, item_id, date_from, date_to, godown_id)


# ================================================================= banking
@router.get("/accounts/banking/accounts", response_model=list[BankAccountOut])
async def bank_accounts(ctx: BkR, db: TenantDB) -> list[BankAccountOut]:
    return await banking.list_bank_accounts(db, ctx)


@router.get("/accounts/banking/cheque-books", response_model=list[ChequeBookOut])
async def cheque_books(ctx: BkR, db: TenantDB, bank_ledger_id: uuid.UUID | None = None) -> list[ChequeBookOut]:
    return await banking.list_cheque_books(db, ctx, bank_ledger_id)


@router.post("/accounts/banking/cheque-books", response_model=ChequeBookOut, status_code=CREATED)
async def create_cheque_book(body: ChequeBookIn, ctx: BkW, db: TenantDB, idem: Idem) -> ChequeBookOut:
    return await idem.save(await banking.create_cheque_book(db, ctx, body), 201)


@router.get("/accounts/banking/cheques", response_model=list[ChequeOut])
async def cheques(ctx: BkR, db: TenantDB, bank_ledger_id: uuid.UUID | None = None, date_from: date | None = None,
                  date_to: date | None = None) -> list[ChequeOut]:  # fmt: skip
    return await banking.list_cheques(db, ctx, bank_ledger_id, date_from, date_to)


@router.get("/accounts/banking/cheques/{entry_id}/print", response_class=Response)
async def print_cheque(entry_id: uuid.UUID, ctx: BkR, db: TenantDB) -> Response:
    data, name = await banking.print_cheque(db, ctx, entry_id)
    return _file(data, "application/pdf", name)


@router.patch("/accounts/banking/entries/{entry_id}/reconcile", response_model=ReconEntryOut)
async def reconcile(entry_id: uuid.UUID, body: ReconcileIn, ctx: BkW, db: TenantDB) -> ReconEntryOut:
    return await banking.reconcile_entry(db, ctx, entry_id, body.bank_reconciliation_date)


@router.post("/accounts/banking/statement-lines/{line_id}/match", response_model=StatementLineOut)
async def match(line_id: uuid.UUID, body: MatchIn, ctx: BkW, db: TenantDB) -> StatementLineOut:
    return await banking.match_line(db, ctx, line_id, body.entry_id)


@router.post("/accounts/banking/statement-lines/{line_id}/unmatch", response_model=StatementLineOut)
async def unmatch(line_id: uuid.UUID, ctx: BkW, db: TenantDB) -> StatementLineOut:
    return await banking.unmatch_line(db, ctx, line_id)


@router.post("/accounts/banking/statement-lines/{line_id}/ignore", response_model=StatementLineOut)
async def ignore(line_id: uuid.UUID, ctx: BkW, db: TenantDB) -> StatementLineOut:
    return await banking.ignore_line(db, ctx, line_id)


@router.get("/accounts/banking/{ledger_id}/reconciliation", response_model=ReconciliationOut)
async def reconciliation(ledger_id: uuid.UUID, ctx: BkR, db: TenantDB, as_of: date = Query(), show: str | None = None
                         ) -> ReconciliationOut:  # fmt: skip
    return await banking.reconciliation(db, ctx, ledger_id, as_of, show)


@router.post("/accounts/banking/{ledger_id}/statements/import", response_model=StatementImportOut, status_code=CREATED)
async def import_statement(ledger_id: uuid.UUID, ctx: BkW, db: TenantDB, file: UploadFile = File(...)
                           ) -> StatementImportOut:  # fmt: skip
    data = await file.read(banking.MAX_STATEMENT_BYTES + 1)
    return await banking.import_statement(db, ctx, ledger_id, data, file.filename)


@router.get("/accounts/banking/{ledger_id}/statement-lines", response_model=Page[StatementLineOut])
async def statement_lines(ledger_id: uuid.UUID, ctx: BkR, db: TenantDB, page: Paging, status: str | None = None
                          ) -> Page[StatementLineOut]:  # fmt: skip
    return await banking.statement_lines(db, ctx, ledger_id, status, page)


# ================================================================= reports / dashboard / utilities
@router.get("/accounts/dashboard", response_model=AccountsDashboardOut)
async def dashboard(ctx: DashR, db: TenantDB) -> AccountsDashboardOut:
    return await reports.dashboard(db, ctx)


@router.get("/accounts/reports/trial-balance", response_model=TrialBalanceOut)
async def trial_balance(ctx: RpR, db: TenantDB, date_from: date = Query(), date_to: date = Query(),
                        mode: str | None = None) -> TrialBalanceOut:  # fmt: skip
    return await reports.trial_balance(db, ctx, date_from, date_to, mode)


@router.get("/accounts/reports/profit-loss", response_model=ProfitLossOut)
async def profit_loss(ctx: RpR, db: TenantDB, date_from: date = Query(), date_to: date = Query()) -> ProfitLossOut:
    return await reports.profit_loss(db, ctx, date_from, date_to)


@router.get("/accounts/reports/balance-sheet", response_model=BalanceSheetOut)
async def balance_sheet(ctx: RpR, db: TenantDB, as_of: date = Query()) -> BalanceSheetOut:
    return await reports.balance_sheet(db, ctx, as_of)


@router.get("/accounts/reports/cash-flow", response_model=CashFlowOut)
async def cash_flow(ctx: RpR, db: TenantDB, date_from: date = Query(), date_to: date = Query()) -> CashFlowOut:
    return await reports.cash_flow(db, ctx, date_from, date_to)


@router.get("/accounts/reports/ratios", response_model=list[RatioOut])
async def ratios(ctx: RpR, db: TenantDB, date_from: date = Query(), date_to: date = Query()) -> list[RatioOut]:
    return await reports.ratios(db, ctx, date_from, date_to)


@router.get("/accounts/reports/ageing", response_model=AgeingOut)
async def ageing(ctx: RpR, db: TenantDB, kind: str = Query(), as_of: date = Query(), buckets: str | None = None
                 ) -> AgeingOut:  # fmt: skip
    return await reports.ageing(db, ctx, kind, as_of, buckets)


@router.get("/accounts/reports/day-book", response_model=Page[VoucherSummary])
async def day_book(ctx: RpR, db: TenantDB, page: Paging, date_from: date = Query(), date_to: date = Query()
                   ) -> Page[VoucherSummary]:  # fmt: skip
    return await reports.day_book(db, ctx, date_from, date_to, page)


@router.get("/accounts/reports/batch-costing", response_model=list[BatchCostRow])
async def batch_costing(
    ctx: RpR, db: TenantDB, date_from: date = Query(), date_to: date = Query()
) -> list[BatchCostRow]:
    return await reports.batch_costing(db, ctx, date_from, date_to)


@router.get("/accounts/reports/{report}/export", response_class=Response)
async def export_report(report: str, ctx: RpR, db: TenantDB, fmt: str = Query(alias="format"),
                        date_from: date | None = None, date_to: date | None = None, as_of: date | None = None,
                        kind: str | None = None) -> Response:  # fmt: skip
    data, mime, name = await reports.export_report(db, ctx, report, fmt, {"date_from": date_from, "date_to": date_to,
                                                                          "as_of": as_of, "kind": kind})  # fmt: skip
    return _file(data, mime, name)


@router.get("/accounts/utilities/exceptions", response_model=list[ExceptionOut])
async def exceptions(ctx: RpR, db: TenantDB) -> list[ExceptionOut]:
    return await reports.exceptions(db, ctx)


@router.get("/accounts/utilities/tally-export", response_class=Response)
async def tally_export(ctx: RpF, db: TenantDB, date_from: date = Query(), date_to: date = Query()) -> Response:
    data, name = await tally_xml.tally_export(db, ctx, date_from, date_to)
    return _file(data, "application/xml", name)
