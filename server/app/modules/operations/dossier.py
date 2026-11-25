"""Run dossier export (spec 02 §4): P1 specs + summary + sign-offs, P2 Dr/Cr money flow + unit cost,
P3 executed flowchart (vector SVG in PDF; table in DOCX) + step log, P4+ step reports + attachment index."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.export import Letterhead, Report, get_exporter
from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import NotFoundError, ValidationFailedError
from app.core.money import to_str
from app.modules.accounts import interface as accounts
from app.modules.documents import interface as documents
from app.modules.operations import graph as g
from app.modules.operations import service_runs as runs_svc
from app.modules.operations.common import assert_run_access, get_run
from app.modules.operations.schemas import RunOut
from app.modules.organization import interface as organization

STATUS_FILL = {"PASSED": "#E7F8EF", "LOCKED": "#E0EAFF", "SKIPPED": "#F2F4F7", "REJECTED": "#FEE4E2",
               "ACTIVE": "#FEF0C7", "PENDING": "#FFFFFF"}  # fmt: skip
NODE_W, NODE_H, GAP_X, GAP_Y = 120, 44, 50, 26


def _h(text: str, level: int = 2) -> dict[str, Any]:
    return {"type": "heading", "data": {"text": text, "level": level}}


def _kv(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    return {"type": "kv", "data": {"rows": [{"label": k, "value": "" if v is None else str(v)} for k, v in rows]}}


def _table(cols: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {
        "type": "table",
        "data": {"columns": cols, "rows": [["" if c is None else str(c) for c in r] for r in rows]},
    }


def _layers(graph: dict[str, Any]) -> dict[str, int]:
    order = g.topological_order(graph)
    layer = dict.fromkeys(order, 0)
    for nid in order:
        for e in g.out_edges(graph, nid, g.FORWARD):
            if e["target"] in layer:
                layer[e["target"]] = max(layer[e["target"]], layer[nid] + 1)
    return layer


def _taken(edge: dict[str, Any], steps: dict[str, Any]) -> bool:
    s = steps.get(edge["source"])
    if s is None:
        return False
    branch = edge.get("branch") or "PASS"
    qty = {"PASS": s.accepted_qty, "DEFAULT": s.accepted_qty, "REJECT": s.rejected_qty, "REWORK": s.rework_qty}
    return bool(qty.get(branch)) and qty[branch] > 0


def flowchart_svg(graph: dict[str, Any], steps: dict[str, Any]) -> bytes:
    """Left-to-right layered diagram: ovals, rectangles, diamonds, double-bordered parallels, terminators;
    edges actually taken in the run are drawn thick in terracotta, REWORK/REJECT dashed."""
    layer = _layers(graph)
    cols: dict[int, list[str]] = {}
    for nid in g.topological_order(graph):
        cols.setdefault(layer.get(nid, 0), []).append(nid)
    pos: dict[str, tuple[float, float]] = {}
    for c, ids in cols.items():
        for r, nid in enumerate(ids):
            pos[nid] = (20 + c * (NODE_W + GAP_X), 30 + r * (NODE_H + GAP_Y))
    width = 40 + max(len(cols), 1) * (NODE_W + GAP_X)
    height = 80 + max((len(v) for v in cols.values()), default=1) * (NODE_H + GAP_Y)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}">']  # fmt: skip
    for e in g.edges_of(graph):
        if e.get("source") not in pos or e.get("target") not in pos:
            continue
        (x1, y1), (x2, y2) = pos[e["source"]], pos[e["target"]]
        taken = _taken(e, steps)
        color, sw = ("#C35E49", 2.5) if taken else ("#98A2B3", 1)
        dash = ' stroke-dasharray="4,3"' if e.get("branch") in ("REWORK", "REJECT") else ""
        if e.get("branch") == "REWORK":
            sx, ex = x1 + NODE_W / 2, x2 + NODE_W / 2
            low = max(y1, y2) + NODE_H + 16
            out.append(f'<path d="M {sx} {y1 + NODE_H} C {sx} {low}, {ex} {low}, {ex} {y2 + NODE_H}" fill="none" '
                       f'stroke="{color}" stroke-width="{sw}"{dash}/>')  # fmt: skip
        else:
            out.append(f'<line x1="{x1 + NODE_W}" y1="{y1 + NODE_H / 2}" x2="{x2}" y2="{y2 + NODE_H / 2}" '
                       f'stroke="{color}" stroke-width="{sw}"{dash}/>')  # fmt: skip
            out.append(f'<circle cx="{x2}" cy="{y2 + NODE_H / 2}" r="2.5" fill="{color}"/>')
    for n in g.nodes_of(graph):
        nid = n["id"]
        if nid not in pos:
            continue
        x, y = pos[nid]
        st = steps.get(nid)
        fill = STATUS_FILL.get(getattr(st, "status", "PENDING"), "#FFFFFF")
        shape = n.get("shape")
        common = f'fill="{fill}" stroke="#1D2939" stroke-width="1"'
        if shape in ("OVAL", "TERMINATOR"):
            rx = NODE_H / 2 if shape == "OVAL" else 8
            out.append(f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="{rx}" {common}/>')
        elif shape == "DIAMOND":
            cx, cy = x + NODE_W / 2, y + NODE_H / 2
            out.append(f'<polygon points="{cx},{y - 6} {x + NODE_W},{cy} {cx},{y + NODE_H + 6} {x},{cy}" {common}/>')
        else:
            out.append(f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" {common}/>')
            if shape == "PARALLEL":
                out.append(f'<rect x="{x + 4}" y="{y + 4}" width="{NODE_W - 8}" height="{NODE_H - 8}" '
                           f'fill="none" stroke="#1D2939" stroke-width="0.8"/>')  # fmt: skip
        label = escape(str(n.get("label") or nid)[:24])
        out.append(f'<text x="{x + NODE_W / 2}" y="{y + NODE_H / 2 + 3}" font-size="8" text-anchor="middle" '
                   f'fill="#141414">{label}</text>')  # fmt: skip
    out.append("</svg>")
    return "".join(out).encode()


def build_blocks(run: RunOut, item: Any, org_name: str, attachments: list[Any], fmt: str) -> tuple[list[dict], dict]:
    images: dict[str, bytes] = {}
    p1: list[dict[str, Any]] = [_h("1. Specification & period summary")]
    if item is not None:
        p1.append(_kv([("Item", item.name), ("SKU", item.sku_code), ("UoM", item.uom_primary),
                       ("HSN/SAC", item.hsn_sac_code)]
                      + [(f"{k}", v) for k, v in (item.custom_fields or {}).items()]))  # fmt: skip
    p1.append(_kv([("Run", run.run_title), ("Period", run.period_month.strftime("%B %Y")), ("Status", run.status),
                   ("Workflow", f"{run.workflow_name} v{run.workflow_version}"),
                   ("Planned qty", to_str(run.planned_qty)), ("Accepted qty", to_str(run.accepted_qty)),
                   ("Rejected qty", to_str(run.rejected_qty)), ("Rework qty", to_str(run.rework_qty)),
                   ("Yield %", to_str(run.yield_pct) if run.yield_pct is not None else "-")]))  # fmt: skip
    signers = {s.step_name: s.signed_off_by_name for s in run.steps if s.signed_off_by_name}
    p1.append(_h("Sign-offs", 3))
    p1.append(_table(["Step", "Signed off by", "At"], [[s.step_name, s.signed_off_by_name, s.signed_off_at]
                                                        for s in run.steps if s.signed_off_by_name] or [["-", "-", "-"]]))  # fmt: skip
    p1.append({"type": "signature", "data": {"roles": ["Production Manager", "QA Lead", "Accountant"],
                                             "signers": signers}})  # fmt: skip
    mf = run.money_flow
    p2 = [{"type": "page_break", "data": {}}, _h("2. Money flow (Dr / Cr) & unit cost"),
          _h("Debits", 3), _table(["Date", "Source", "Voucher", "Particulars", "Amount"],
                                  [[d.date, d.source, d.voucher_number, d.particulars, to_str(d.amount)] for d in mf.debits]
                                  or [["-", "-", "-", "No debits", "0.00"]]),
          _h("Credits", 3), _table(["Date", "Source", "Voucher", "Particulars", "Amount"],
                                   [[c.date, c.source, c.voucher_number, c.particulars, to_str(c.amount)] for c in mf.credits]
                                   or [["-", "-", "-", "No credits", "0.00"]]),
          _kv([("Total debit", to_str(mf.total_debit)), ("Total credit", to_str(mf.total_credit)),
               ("Net run cost", to_str(mf.net_cost)), ("Accepted qty", to_str(mf.accepted_qty)),
               ("Unit manufacturing cost", to_str(mf.unit_cost))])]  # fmt: skip
    p3: list[dict[str, Any]] = [{"type": "page_break", "data": {}}, _h("3. Executed flowchart & step log")]
    steps_by_node = {s.node_id: s for s in run.steps}
    if fmt == "pdf":
        images["flowchart"] = flowchart_svg(run.graph_snapshot, steps_by_node)
        p3.append({"type": "image", "data": {"ref": "flowchart", "width_mm": 180}})
    else:
        p3.append(_table(["From", "Branch", "To", "Taken"], [
            [e.get("source"), e.get("branch"), e.get("target"), "yes" if _taken(e, steps_by_node) else ""]
            for e in g.edges_of(run.graph_snapshot)]))  # fmt: skip
    p3.append(_table(["#", "Step", "Status", "In", "Acc", "Rej", "Rwk", "Branch", "Executed by", "At", "QC readings"],
                     [[s.sequence, s.step_name, s.status, to_str(s.input_qty), to_str(s.accepted_qty),
                       to_str(s.rejected_qty), to_str(s.rework_qty), s.branch_taken, s.executed_by_name,
                       s.executed_at.strftime("%Y-%m-%d %H:%M") if s.executed_at else "",
                       "; ".join(f"{k}={v.value}{'*' if v.auto_filled else ''}" for k, v in s.qc_measurements.items())]
                      for s in run.steps]))  # fmt: skip
    p3.append({"type": "paragraph", "data": {"text": "* = auto-filled by Quick QC (nominal value)."}})
    p4: list[dict[str, Any]] = [{"type": "page_break", "data": {}}, _h("4. Step reports & attachments")]
    p4.append(_table(["Title", "Type", "File", "Step", "Revision", "Status"],
                     [[a.title, a.source_type, a.file_name, a.step_name, a.revision_no, a.approval_status]
                      for a in attachments] or [["No attachments", "", "", "", "", ""]]))  # fmt: skip
    return [*p1, *p2, *p3, *p4], images


async def export_dossier(
    db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, fmt: str, save: bool
) -> tuple[bytes, str, str]:
    fmt = (fmt or "").lower()
    if fmt not in ("pdf", "docx"):
        raise ValidationFailedError("format must be pdf or docx")
    run = await get_run(db, ctx, run_id)
    await assert_run_access(ctx, db, run, "READ")
    out = await runs_svc.run_out(db, ctx, run)
    item = await accounts.get_stock_item(db, ctx, run.stock_item_id) if run.stock_item_id else None
    org = await organization.get_org_brief(db, ctx.org_id)
    if org is None:
        raise NotFoundError()
    step_names = {s.id: s.step_name for s in out.steps}
    attachments = await documents.list_run_attachments(db, ctx, run.id, step_names)
    blocks, images = build_blocks(out, item, org.legal_name, attachments, fmt)
    report = Report(title=f"Batch Dossier — {run.run_title}", blocks=blocks, images=images,
                    letterhead=Letterhead(name=org.legal_name, lines=[*org.address_lines[:2],
                                          f"GSTIN {org.gstin or '-'}"]),
                    footer=f"{org.legal_name} · {run.run_title} · generated {date.today().isoformat()}")  # fmt: skip
    exporter = get_exporter()
    data = exporter.render(report, fmt)
    mime = exporter.mime(fmt)
    file_name = f"Dossier - {run.run_title}.{fmt}"
    if save and run.doc_folder_id:
        await documents.store_generated_file(db, ctx, folder_id=run.doc_folder_id, title=f"Dossier - {run.run_title}",
                                             mime=mime, data=data, source_type="GENERATED_REPORT",
                                             file_name=file_name, linked_period_run_id=run.id)  # fmt: skip
    await write_audit(db, ctx, "OPERATIONS", "EXPORT", "period_run", run.id, after={"format": fmt, "saved": save})
    return data, mime, file_name
