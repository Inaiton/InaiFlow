"""Taxation DTOs — names/fields exactly as contract section "accounts: taxation"."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from app.core.money import DecimalStr
from app.core.schemas import InModel, OutModel


class GstTotals(OutModel):
    taxable: DecimalStr
    cgst: DecimalStr
    sgst: DecimalStr
    igst: DecimalStr
    cess: DecimalStr


class GstSummaryOut(OutModel):
    period: str
    outward: GstTotals
    inward_itc: GstTotals
    rcm_liability: GstTotals
    net_payable: GstTotals
    voucher_count: int


class GstValidationIssue(OutModel):
    voucher_id: uuid.UUID | None
    voucher_number: str | None
    severity: str
    code: str
    message: str


class Gstr1Out(OutModel):
    period: str
    gstin: str | None
    b2b: list[Any]
    b2cl: list[Any]
    b2cs: list[Any]
    cdnr: list[Any]
    cdnur: list[Any]
    exp: list[Any]
    hsn: list[Any]
    totals: GstTotals
    errors: list[GstValidationIssue]


class Gstr3bOut(OutModel):
    period: str
    sec_3_1: Any
    sec_3_2: Any
    sec_4: Any
    sec_5: Any
    sec_6_1: Any


class Gstr2bImportOut(OutModel):
    import_id: uuid.UUID
    period: str
    invoices: int


class ReconRow(OutModel):
    gstin: str
    supplier_name: str | None
    invoice_no: str
    invoice_date: date
    taxable: DecimalStr
    tax: DecimalStr
    voucher_id: uuid.UUID | None
    portal_taxable: DecimalStr | None
    portal_tax: DecimalStr | None
    difference: DecimalStr | None


class Gstr2bReconOut(OutModel):
    period: str
    exact: list[ReconRow]
    partial: list[ReconRow]
    missing_in_books: list[ReconRow]
    missing_in_portal: list[ReconRow]


class EinvoiceOut(OutModel):
    voucher_id: uuid.UUID
    kind: str
    status: str
    irn: str | None
    ack_no: str | None
    ack_date: datetime | None
    signed_qr: str | None
    eway_bill_no: str | None
    valid_until: datetime | None


class EinvoiceCancelIn(InModel):
    reason_code: Literal["1", "2", "3", "4"]
    remarks: str = Field(min_length=1, max_length=100)


class EwayBillIn(InModel):
    transporter_id: str | None = Field(default=None, max_length=15)
    transporter_name: str | None = Field(default=None, max_length=100)
    vehicle_no: str | None = Field(default=None, max_length=15)
    distance_km: int = Field(ge=0, le=4000)
    transport_mode: Literal["ROAD", "RAIL", "AIR", "SHIP"]


class TdsComputeIn(InModel):
    section: str
    party_ledger_id: uuid.UUID
    amount: DecimalStr = Field(gt=0)
    voucher_date: date


class TdsComputeOut(OutModel):
    applicable: bool
    section: str
    rate: DecimalStr
    tds_amount: DecimalStr
    threshold_info: str
    pan_available: bool


class TdsSummaryRow(OutModel):
    section: str
    party_ledger_id: uuid.UUID
    party_name: str
    pan: str | None
    amount_paid: DecimalStr
    tds_amount: DecimalStr
    deposited: bool


class TdsChallanOut(OutModel):
    month: str
    due_date: date
    by_section: list[Any]
    total: DecimalStr


class TdsSectionOut(OutModel):
    section: str
    nature: str
    threshold_single: DecimalStr | None
    threshold_annual: DecimalStr | None
    rate_individual: DecimalStr
    rate_company: DecimalStr
    rate_no_pan: DecimalStr
