"""System report templates (DOC_REPORT_TEMPLATES). ``content_schema`` = ``{"blocks": [ReportBlock...]}``.

Block types understood by ``app.adapters.export`` (and the web renderer):
``heading {text, level}``, ``paragraph {text}``, ``kv {rows: [{label, value}]}``,
``table {columns: [str], rows: [[str]]}``, ``qc_table {source: "step"}`` (expands ``{{step.qc_readings}}``),
``signature {roles: [str]}``, ``divider {}``, ``page_break {}``. Text may contain ``{{tokens}}``.
"""

from __future__ import annotations


def _b(i: int, type_: str, **data: object) -> dict:
    return {"id": f"b{i}", "type": type_, "data": data}


_HEADER = [
    _b(1, "heading", text="{{org.legal_name}}", level=1),
    _b(2, "paragraph", text="{{org.address}} | GSTIN {{org.gstin}}"),
    _b(3, "divider"),
]

INCOMING_INSPECTION_REPORT = {
    "key": "incoming-inspection-report",
    "name": "Incoming Inspection Report",
    "description": "Receiving inspection of raw material / bought-out parts (ISO 9001 8.4).",
    "blocks": [*_HEADER,
               _b(4, "heading", text="Incoming Inspection Report", level=2),
               _b(5, "kv", rows=[{"label": "Item", "value": "{{item.name}} ({{item.sku_code}})"},
                                 {"label": "Supplier invoice", "value": "{{voucher.supplier_invoice_no}}"},
                                 {"label": "GRN / Voucher", "value": "{{voucher.number}}"},
                                 {"label": "Batch / Heat No.", "value": "{{step.qc.heat_no}}"},
                                 {"label": "Date", "value": "{{today}}"}]),
               _b(6, "qc_table", source="step", text="{{step.qc_readings}}"),
               _b(7, "paragraph", text="Result: {{step.result}}. Accepted {{step.accepted_qty}}, rejected {{step.rejected_qty}}."),
               _b(8, "signature", roles=["Inspected by", "Approved by"])],
}  # fmt: skip

FIRST_ARTICLE_INSPECTION = {
    "key": "first-article-inspection",
    "name": "First Article Inspection",
    "description": "FAI of the first piece of a period run against drawing characteristics.",
    "blocks": [*_HEADER,
               _b(4, "heading", text="First Article Inspection (FAI)", level=2),
               _b(5, "kv", rows=[{"label": "Part", "value": "{{item.name}}"},
                                 {"label": "Drawing rev.", "value": "{{item.custom.drawing_rev}}"},
                                 {"label": "Material grade", "value": "{{item.custom.material_grade}}"},
                                 {"label": "Run", "value": "{{run.title}} ({{run.period}})"},
                                 {"label": "Step", "value": "{{step.name}}"}]),
               _b(6, "qc_table", source="step", text="{{step.qc_readings}}"),
               _b(7, "paragraph", text="Instrument: {{step.instrument}}. Operator: {{step.executed_by}}."),
               _b(8, "signature", roles=["Inspector", "QA Lead"])],
}  # fmt: skip

NCR_CAPA_FORM = {
    "key": "ncr-capa-form",
    "name": "NCR / CAPA Form",
    "description": "Non-conformance report with root cause and corrective/preventive actions (ISO 9001 10.2).",
    "blocks": [*_HEADER,
               _b(4, "heading", text="Non-Conformance Report & CAPA", level=2),
               _b(5, "kv", rows=[{"label": "NCR No.", "value": "{{ncr.number}}"},
                                 {"label": "Run / Step", "value": "{{run.title}} / {{step.name}}"},
                                 {"label": "Rejected qty", "value": "{{ncr.rejected_qty}}"},
                                 {"label": "Raised on", "value": "{{today}}"}]),
               _b(6, "heading", text="Defect description", level=3),
               _b(7, "paragraph", text="{{ncr.defect_description}}"),
               _b(8, "heading", text="Root cause analysis", level=3),
               _b(9, "paragraph", text="{{ncr.root_cause_analysis}}"),
               _b(10, "table", columns=["Action", "Description", "Owner", "Target date"],
                  rows=[["Corrective", "{{ncr.corrective_action}}", "", ""],
                        ["Preventive", "{{ncr.preventive_action}}", "", ""]]),
               _b(11, "signature", roles=["Raised by", "Verified by", "Closed by"])],
}  # fmt: skip

BATCH_SUMMARY = {
    "key": "batch-summary",
    "name": "Batch Summary",
    "description": "Period run summary: quantities, yield, unit cost and sign-offs.",
    "blocks": [*_HEADER,
               _b(4, "heading", text="Batch Summary — {{run.title}}", level=2),
               _b(5, "kv", rows=[{"label": "Item", "value": "{{item.name}}"},
                                 {"label": "Period", "value": "{{run.period}}"},
                                 {"label": "Planned qty", "value": "{{run.planned_qty}}"},
                                 {"label": "Accepted / Rejected / Rework",
                                  "value": "{{run.accepted_qty}} / {{run.rejected_qty}} / {{run.rework_qty}}"},
                                 {"label": "Yield", "value": "{{run.yield_pct}}%"},
                                 {"label": "Total cost", "value": "{{accounts.total_cost}}"},
                                 {"label": "Unit manufacturing cost", "value": "{{accounts.unit_cost}}"}]),
               _b(6, "paragraph", text="Workflow: {{run.workflow_name}} v{{run.workflow_version}}."),
               _b(7, "signature", roles=["Production Manager", "QA Lead", "Accountant"])],
}  # fmt: skip

DOC_REPORT_TEMPLATES: list[dict] = [
    INCOMING_INSPECTION_REPORT,
    FIRST_ARTICLE_INSPECTION,
    NCR_CAPA_FORM,
    BATCH_SUMMARY,
]
