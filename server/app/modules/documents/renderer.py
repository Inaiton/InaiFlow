"""Pure report-template rendering: ``{{token}}`` substitution over block JSON (no code execution).

``render_content(content, values)`` walks every string inside each block's ``data`` and replaces tokens with
``values[token]``. Unknown tokens render empty and are reported in ``warnings``; known tokens with no value
in the given context render empty with a "no value" warning. ``qc_table`` blocks with ``source = "step"``
are expanded into ``columns`` / ``rows`` from ``qc_rows``.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from typing import Any

TOKEN_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}")
QC_COLUMNS = ["Parameter", "Nominal", "Tolerance", "Observed", "Result"]

TOKEN_CATALOGUE: list[tuple[str, str, str, str]] = [
    # token, label, group, sample
    ("today", "Today's date", "general", "2026-09-15"),
    ("org.legal_name", "Legal name", "org", "Precision Components Pvt Ltd"),
    ("org.trade_name", "Trade / mailing name", "org", "Precision Components"),
    ("org.address", "Address", "org", "12 Industrial Estate, Coimbatore - 641021, Tamil Nadu"),
    ("org.gstin", "GSTIN", "org", "33ABCDE1234F1Z5"),
    ("org.pan", "PAN", "org", "ABCDE1234F"),
    ("org.phone", "Phone", "org", "+91 98400 00000"),
    ("org.email", "Email", "org", "accounts@example.com"),
    ("item.name", "Item name", "item", "Component 1"),
    ("item.sku_code", "SKU / part number", "item", "CMP-001"),
    ("item.uom", "Unit of measure", "item", "NOS"),
    ("item.hsn_sac_code", "HSN/SAC", "item", "8483"),
    ("item.target_type", "Target type", "item", "STOCK_ITEM"),
    ("item.custom.<field>", "Custom field (e.g. item.custom.drawing_rev)", "item", "Rev C"),
    ("run.title", "Run title", "run", "Component 1 - Sep 2026"),
    ("run.period", "Run period", "run", "Sep 2026"),
    ("run.status", "Run status", "run", "IN_PROGRESS"),
    ("run.planned_qty", "Planned quantity", "run", "500.00"),
    ("run.accepted_qty", "Accepted quantity", "run", "485.00"),
    ("run.rejected_qty", "Rejected quantity", "run", "15.00"),
    ("run.rework_qty", "Rework quantity", "run", "0.00"),
    ("run.yield_pct", "Yield %", "run", "97.00"),
    ("run.workflow_name", "Workflow name", "run", "CNC Machining with Final Inspection"),
    ("run.workflow_version", "Workflow version", "run", "2"),
    ("run.started_at", "Started at", "run", "2026-09-01"),
    ("run.completed_at", "Completed at", "run", "2026-09-28"),
    ("step.name", "Step name", "step", "In-process QC"),
    ("step.status", "Step status", "step", "PASSED"),
    ("step.result", "Step result (branch taken)", "step", "PASS"),
    ("step.input_qty", "Step input quantity", "step", "500.00"),
    ("step.accepted_qty", "Step accepted quantity", "step", "485.00"),
    ("step.rejected_qty", "Step rejected quantity", "step", "15.00"),
    ("step.rework_qty", "Step rework quantity", "step", "0.00"),
    ("step.executed_by", "Executed by", "step", "Ravi Kumar"),
    ("step.executed_at", "Executed at", "step", "2026-09-10 10:30"),
    ("step.signed_off_by", "Signed off by", "step", "Priya QA"),
    ("step.instrument", "Instrument used", "step", "VC-01 Vernier Caliper"),
    ("step.notes", "Step notes", "step", ""),
    ("step.qc_readings", "QC readings (table)", "step", "OD: 25.00 mm (OK)"),
    ("step.qc.<field>", "One QC reading (e.g. step.qc.od)", "step", "25.00"),
    ("ncr.number", "NCR number", "ncr", "NCR-2026-0001"),
    ("ncr.rejected_qty", "NCR rejected quantity", "ncr", "15.00"),
    ("ncr.defect_description", "Defect description", "ncr", "OD oversize"),
    ("ncr.root_cause_analysis", "Root cause", "ncr", ""),
    ("ncr.corrective_action", "Corrective action", "ncr", ""),
    ("ncr.preventive_action", "Preventive action", "ncr", ""),
    ("ncr.status", "NCR status", "ncr", "OPEN"),
    ("voucher.number", "Voucher number", "voucher", "PUR-0012"),
    ("voucher.date", "Voucher date", "voucher", "2026-09-03"),
    ("voucher.type", "Voucher type", "voucher", "Purchase"),
    ("voucher.party", "Party", "voucher", "Steel Traders"),
    ("voucher.amount", "Voucher amount", "voucher", "250000.00"),
    ("voucher.supplier_invoice_no", "Supplier invoice no.", "voucher", "INV-889"),
    ("accounts.total_cost", "Run net cost", "accounts", "125000.00"),
    ("accounts.total_debit", "Run total debits", "accounts", "130000.00"),
    ("accounts.total_credit", "Run total credits", "accounts", "5000.00"),
    ("accounts.unit_cost", "Unit manufacturing cost", "accounts", "257.73"),
]
STATIC_TOKENS = frozenset(t for t, *_ in TOKEN_CATALOGUE if "<" not in t)
DYNAMIC_PREFIXES = ("item.custom.", "step.qc.")


def is_known_token(token: str) -> bool:
    return token in STATIC_TOKENS or any(token.startswith(p) and len(token) > len(p) for p in DYNAMIC_PREFIXES)


def tokens_in(content: Any) -> set[str]:
    found: set[str] = set()

    def walk(v: Any) -> None:
        if isinstance(v, str):
            found.update(TOKEN_RE.findall(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(content)
    return found


def qc_readings_text(rows: list[list[str]]) -> str:
    return "; ".join(f"{r[0]}: {r[3] or '-'} ({r[4]})" for r in rows) if rows else ""


def render_content(
    content: dict[str, Any] | None,
    values: dict[str, str | None],
    *,
    qc_rows: list[list[str]] | None = None,
    known: Callable[[str], bool] = is_known_token,
) -> tuple[dict[str, Any], list[str]]:
    """Return (rendered content, warnings). ``content`` is ``{"blocks": [...]}``; input is not mutated."""
    out = copy.deepcopy(content or {"blocks": []})
    warnings: list[str] = []
    rows = qc_rows or []
    vals = dict(values)
    vals.setdefault("step.qc_readings", qc_readings_text(rows) if qc_rows is not None else None)

    def sub(match: re.Match[str]) -> str:
        token = match.group(1)
        if not known(token):
            _warn(f"Unknown token {{{{{token}}}}}")
            return ""
        value = vals.get(token)
        if value is None:
            _warn(f"No value for {{{{{token}}}}} in this context")
            return ""
        return str(value)

    def _warn(msg: str) -> None:
        if msg not in warnings:
            warnings.append(msg)

    def walk(v: Any) -> Any:
        if isinstance(v, str):
            return TOKEN_RE.sub(sub, v)
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v

    blocks = []
    for block in out.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        b = dict(block)
        data = walk(b.get("data") or {})
        if b.get("type") == "qc_table" and (data.get("source") == "step" or not data.get("columns")):
            if qc_rows is None:
                _warn("QC table needs a run step in the context")
            data = {**data, "columns": list(QC_COLUMNS), "rows": [list(r) for r in rows]}
        b["data"] = data
        blocks.append(b)
    out["blocks"] = blocks
    return out, warnings
