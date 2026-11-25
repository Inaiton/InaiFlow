"""Report template token catalogue (plan §3.8 "Template rendering").

Single source for ``GET /admin/meta/template-tokens`` and — via ``superadmin.interface.TEMPLATE_TOKENS`` —
for the documents module's ``GET /documents/template-tokens`` (requested from S4, see decisions/S5.md).
Covers every token used by the seeded report templates (``app/seeds/doc_templates.py``).
"""

from __future__ import annotations

from typing import NamedTuple


class TemplateToken(NamedTuple):
    token: str
    label: str
    group: str
    sample: str


def _t(token: str, label: str, sample: str) -> TemplateToken:
    """``token`` is inserted verbatim by the editors, so it carries the braces: ``{{org.legal_name}}``."""
    return TemplateToken(f"{{{{{token}}}}}", label, token.split(".")[0] if "." in token else "general", sample)


TEMPLATE_TOKENS: tuple[TemplateToken, ...] = (
    # organization
    _t("org.legal_name", "Organization legal name", "Precision Components Pvt Ltd"),
    _t("org.trade_name", "Trade / mailing name", "Precision Components"),
    _t("org.address", "Organization address", "12 Industrial Estate, Coimbatore - 641021, Tamil Nadu"),
    _t("org.gstin", "Organization GSTIN", "33ABCDE1234F1Z5"),
    _t("org.pan", "Organization PAN", "ABCDE1234F"),
    _t("org.phone", "Contact phone", "+91 98400 00000"),
    _t("org.email", "Contact email", "accounts@example.com"),
    # stock item / process target
    _t("item.name", "Item name", "Component 1"),
    _t("item.sku_code", "Item SKU / part code", "CMP-001"),
    _t("item.uom", "Unit of measure", "Nos"),
    _t("item.hsn_sac", "HSN / SAC code", "8483"),
    _t("item.custom.drawing_rev", "Drawing revision (custom field)", "Rev C"),
    _t("item.custom.material_grade", "Material grade (custom field)", "EN8"),
    # period run
    _t("run.title", "Run title", "Component 1 - Sept 2026"),
    _t("run.period", "Run period", "Sept 2026"),
    _t("run.status", "Run status", "IN_PROGRESS"),
    _t("run.planned_qty", "Planned quantity", "500"),
    _t("run.accepted_qty", "Accepted quantity", "485"),
    _t("run.rejected_qty", "Rejected quantity", "15"),
    _t("run.rework_qty", "Rework quantity", "0"),
    _t("run.yield_pct", "Yield %", "97.00"),
    _t("run.workflow_name", "Workflow name", "CNC Machining Flow"),
    _t("run.workflow_version", "Workflow version", "2"),
    # step
    _t("step.name", "Step name", "CNC Machining"),
    _t("step.result", "Step result", "PASSED"),
    _t("step.input_qty", "Step input quantity", "500"),
    _t("step.accepted_qty", "Step accepted quantity", "485"),
    _t("step.rejected_qty", "Step rejected quantity", "15"),
    _t("step.rework_qty", "Step rework quantity", "0"),
    _t("step.qc_readings", "QC readings table", "OD 25.01 mm (25.00 ±0.02) PASS"),
    _t("step.qc.heat_no", "QC field value (step.qc.<field>)", "H-2291"),
    _t("step.instrument", "Instrument used", "Vernier VC-07"),
    _t("step.executed_by", "Executed by", "Ravi Kumar"),
    _t("step.executed_at", "Executed at", "2026-09-14 10:32"),
    # accounts
    _t("accounts.total_cost", "Run total cost", "245000.00"),
    _t("accounts.unit_cost", "Unit manufacturing cost", "505.15"),
    _t("accounts.material_cost", "Raw material cost", "180000.00"),
    _t("accounts.labour_cost", "Allocated direct labour", "45000.00"),
    _t("accounts.scrap_credit", "Scrap credit", "1200.00"),
    # linked voucher
    _t("voucher.number", "Voucher number", "PUR-0042"),
    _t("voucher.date", "Voucher date", "2026-09-02"),
    _t("voucher.party", "Party name", "Steel Traders"),
    _t("voucher.supplier_invoice_no", "Supplier invoice no.", "ST/2026/118"),
    _t("voucher.amount", "Voucher amount", "250000.00"),
    # NCR / CAPA
    _t("ncr.number", "NCR number", "NCR-0007"),
    _t("ncr.rejected_qty", "NCR rejected quantity", "15"),
    _t("ncr.defect_description", "Defect description", "OD oversize beyond tolerance"),
    _t("ncr.root_cause_analysis", "Root cause analysis", "Tool wear on insert T04"),
    _t("ncr.corrective_action", "Corrective action", "Replace insert, re-qualify setup"),
    _t("ncr.preventive_action", "Preventive action", "Tool-life counter at 400 parts"),
    _t("ncr.status", "NCR status", "OPEN"),
    # general
    _t("today", "Today's date", "2026-09-14"),
    _t("user.name", "Current user", "Olivia Owner"),
)
