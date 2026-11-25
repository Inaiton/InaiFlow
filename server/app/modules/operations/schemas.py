"""Operations contract models (names match docs/api/contract.api exactly).

Shared models owned by other modules (``StockItemIn``, ``BomComponent``, ``KpiOut``, ``InvitationOut``) are
taken from those modules' interfaces when exported, otherwise identical local copies are used (identical
JSON schemas merge into one OpenAPI component).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import EmailStr, Field

from app.core.money import DecimalStr
from app.core.schemas import InModel, OutModel
from app.modules.accounts import interface as _accounts
from app.modules.operations import _shared
from app.modules.organization import interface as _organization

NodeShape = Literal["OVAL", "RECTANGLE", "DIAMOND", "PARALLEL", "TERMINATOR"]
Branch = Literal["PASS", "REJECT", "REWORK", "DEFAULT"]
StepStatus = Literal["PENDING", "ACTIVE", "PASSED", "REJECTED", "SKIPPED", "LOCKED"]
RunStatus = Literal["PLANNED", "IN_PROGRESS", "QC_HOLD", "COMPLETED", "CANCELLED"]
DrCr = Literal["DR", "CR"]


# ---------------------------------------------------------------- shared (other modules)
BomComponent: Any = getattr(_accounts, "BomComponent", None) or _shared.BomComponent
StockItemIn: Any = getattr(_accounts, "StockItemIn", None) or _shared.StockItemIn
KpiOut: Any = getattr(_accounts, "KpiOut", None) or _shared.KpiOut
InvitationOut: Any = getattr(_organization, "InvitationOut", None) or _shared.InvitationOut


# ---------------------------------------------------------------- workflow graph
class QcField(InModel):
    key: str = Field(min_length=1, max_length=60)
    label: str
    type: str
    unit: str | None = None
    nominal: DecimalStr | None = None
    tol_minus: DecimalStr | None = None
    tol_plus: DecimalStr | None = None
    options: list[str] | None = None
    required: bool | None = None


class PassCriteria(InModel):
    mode: str
    expression: str | None = None


class NodeConfig(InModel):
    trigger: str | None = None
    assigned_role_code: str | None = None
    machine: str | None = None
    std_cycle_time_mins: DecimalStr | None = None
    instrument_required: bool | None = None
    qc_fields: list[QcField] | None = None
    pass_criteria: PassCriteria | None = None
    reject_action: str | None = None
    sop_document_id: uuid.UUID | None = None
    skippable: bool | None = None
    commit_godown_id: uuid.UUID | None = None
    report_template_id: uuid.UUID | None = None
    notes: str | None = None


class Position(InModel):
    x: DecimalStr
    y: DecimalStr


class WorkflowNode(InModel):
    id: str = Field(min_length=1, max_length=100)
    shape: NodeShape
    label: str
    position: Position
    config: NodeConfig


class WorkflowEdge(InModel):
    id: str = Field(min_length=1, max_length=200)
    source: str
    target: str
    branch: Branch
    label: str | None = None


class WorkflowGraph(InModel):
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class WorkflowSummary(OutModel):
    id: uuid.UUID
    template_key: uuid.UUID
    name: str
    description: str | None
    version: int
    status: str
    stock_item_id: uuid.UUID | None
    stock_item_name: str | None
    iso_clause_ref: str | None
    node_count: int
    active_run_count: int
    published_at: datetime | None
    created_at: datetime


class WorkflowOut(WorkflowSummary):
    graph_definition: Any
    created_by_name: str


class WorkflowIn(InModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    stock_item_id: uuid.UUID | None = None
    iso_clause_ref: str | None = None
    graph_definition: WorkflowGraph | None = None
    from_library_key: str | None = None


class WorkflowUpdateIn(InModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    stock_item_id: uuid.UUID | None = None
    iso_clause_ref: str | None = None
    graph_definition: WorkflowGraph | None = None


class ValidationIssue(OutModel):
    node_id: str | None
    edge_id: str | None
    message: str


class WorkflowValidationOut(OutModel):
    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]


class LibraryTemplateOut(OutModel):
    key: str
    name: str
    description: str
    iso_clause_ref: str | None
    graph_definition: Any


# ---------------------------------------------------------------- items
class ItemStatsOut(OutModel):
    run_count: int
    active_run_count: int
    last_run_at: datetime | None
    avg_yield_pct: DecimalStr | None
    avg_unit_cost: DecimalStr | None


class OpsItemOut(OutModel):
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
    bom_components: list[Any]
    closing_qty: DecimalStr
    closing_value: DecimalStr
    created_at: datetime
    stats: ItemStatsOut
    workflow_count: int


# ---------------------------------------------------------------- runs
class RunCreateIn(InModel):
    workflow_id: uuid.UUID
    run_title: str | None = Field(default=None, max_length=200)
    period_month: date
    planned_qty: DecimalStr
    stock_item_id: uuid.UUID | None = None
    start_now: bool | None = None


class QcReading(OutModel):
    value: str | None
    in_tolerance: bool | None
    auto_filled: bool


class StepOut(OutModel):
    id: uuid.UUID
    node_id: str
    step_name: str
    node_shape: NodeShape
    sequence: int
    status: StepStatus
    input_qty: DecimalStr
    accepted_qty: DecimalStr
    rejected_qty: DecimalStr
    rework_qty: DecimalStr
    qc_measurements: dict[str, QcReading]
    branch_taken: str | None
    quick_qc: bool
    is_locked: bool
    executed_by_name: str | None
    executed_at: datetime | None
    signed_off_by_name: str | None
    signed_off_at: datetime | None
    override_reason: str | None
    skip_reason: str | None
    notes: str | None
    instrument_id: uuid.UUID | None
    ncr_id: uuid.UUID | None
    attachment_count: int


class MoneyFlowLine(OutModel):
    source: str
    voucher_id: uuid.UUID | None
    voucher_number: str | None
    date: date
    particulars: str
    amount: DecimalStr
    step_id: uuid.UUID | None


class MoneyFlowOut(OutModel):
    debits: list[MoneyFlowLine]
    credits: list[MoneyFlowLine]
    total_debit: DecimalStr
    total_credit: DecimalStr
    net_cost: DecimalStr
    accepted_qty: DecimalStr
    unit_cost: DecimalStr


class RunSummary(OutModel):
    id: uuid.UUID
    run_title: str
    period_month: date
    status: RunStatus
    planned_qty: DecimalStr
    accepted_qty: DecimalStr
    rejected_qty: DecimalStr
    rework_qty: DecimalStr
    yield_pct: DecimalStr | None
    computed_unit_cost: DecimalStr
    stock_item_id: uuid.UUID | None
    stock_item_name: str | None
    workflow_id: uuid.UUID
    workflow_name: str
    workflow_version: int
    current_step_names: list[str]
    progress_pct: DecimalStr
    created_at: datetime


class RunOut(RunSummary):
    graph_snapshot: Any
    steps: list[StepOut]
    money_flow: MoneyFlowOut
    cost_centre_id: uuid.UUID | None
    doc_folder_id: uuid.UUID | None
    hold_reason: str | None
    cancel_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_by_name: str


class ReasonIn(InModel):
    reason: str = Field(min_length=1, max_length=2000)


class OptionalReasonIn(InModel):
    reason: str | None = Field(default=None, max_length=2000)


class StepExecuteIn(InModel):
    input_qty: DecimalStr
    accepted_qty: DecimalStr
    rejected_qty: DecimalStr
    rework_qty: DecimalStr | None = None
    measurements: dict[str, str] | None = None
    quick_qc: bool | None = None
    instrument_id: uuid.UUID | None = None
    notes: str | None = None
    override_reason: str | None = None
    defect_description: str | None = None


class NcrOut(OutModel):
    id: uuid.UUID
    ncr_number: str
    period_run_id: uuid.UUID | None
    run_title: str | None
    run_step_id: uuid.UUID | None
    step_name: str | None
    rejected_qty: DecimalStr
    defect_description: str
    root_cause_analysis: str | None
    corrective_action: str | None
    preventive_action: str | None
    verification_notes: str | None
    source: str
    status: str
    assigned_to: uuid.UUID | None
    assigned_to_name: str | None
    closed_by_name: str | None
    closed_at: datetime | None
    created_at: datetime


class StepExecuteOut(OutModel):
    step: StepOut
    run: RunSummary
    activated_step_ids: list[uuid.UUID]
    ncr: NcrOut | None
    stock_voucher_id: uuid.UUID | None


class RunPostingIn(InModel):
    entry_type: DrCr
    amount: DecimalStr
    ledger_id: uuid.UUID
    contra_ledger_id: uuid.UUID
    voucher_date: date
    narration: str | None = None
    step_id: uuid.UUID | None = None


class RunPostingOut(OutModel):
    voucher_id: uuid.UUID
    money_flow: MoneyFlowOut


class LinkVoucherIn(InModel):
    voucher_id: uuid.UUID
    step_id: uuid.UUID | None = None


# ---------------------------------------------------------------- ISO compliance
class NcrIn(InModel):
    period_run_id: uuid.UUID | None = None
    run_step_id: uuid.UUID | None = None
    rejected_qty: DecimalStr
    defect_description: str = Field(min_length=1)
    assigned_to: uuid.UUID | None = None


class NcrUpdateIn(InModel):
    defect_description: str | None = None
    root_cause_analysis: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    assigned_to: uuid.UUID | None = None
    status: str | None = None


class NcrCloseIn(InModel):
    verification_notes: str = Field(min_length=1)


class InstrumentOut(OutModel):
    id: uuid.UUID
    instrument_code: str
    name: str
    location: str | None
    range_spec: str | None
    least_count: str | None
    last_calibrated_date: date
    next_due_date: date
    status: str
    days_to_due: int
    certificate_doc_id: uuid.UUID | None


class InstrumentIn(InModel):
    instrument_code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    location: str | None = None
    range_spec: str | None = None
    least_count: str | None = None
    last_calibrated_date: date
    next_due_date: date
    certificate_doc_id: uuid.UUID | None = None


class CalibrateIn(InModel):
    calibrated_on: date
    next_due_date: date
    certificate_doc_id: uuid.UUID | None = None


class ChecklistItemOut(OutModel):
    id: uuid.UUID
    clause: str
    title: str
    description: str | None
    status: str
    evidence_document_ids: list[uuid.UUID]
    notes: str | None
    updated_by_name: str | None
    updated_at: datetime | None


class ChecklistUpdateIn(InModel):
    status: str | None = None
    evidence_document_ids: list[uuid.UUID] | None = None
    notes: str | None = None


class ClauseScore(OutModel):
    clause: str
    title: str
    total: int
    compliant: int
    score_pct: DecimalStr


class ReadinessOut(OutModel):
    score_pct: DecimalStr
    by_clause: list[ClauseScore]
    open_ncrs: int
    expired_instruments: int


class AuditorInviteIn(InModel):
    email: EmailStr
    access_expires_at: datetime
    stock_item_ids: list[uuid.UUID] | None = None
    period_run_ids: list[uuid.UUID] | None = None


class OpsDashboardOut(OutModel):
    kpis: list[KpiOut]
    active_runs: list[RunSummary]
    open_ncrs: list[NcrOut]
    calibration_due: list[InstrumentOut]
    readiness_pct: DecimalStr
    yield_series: list[Any]
