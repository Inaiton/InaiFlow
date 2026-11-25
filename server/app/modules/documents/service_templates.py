"""Report / monthly-folder-rule templates, token catalogue and server-side rendering with a context."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import NotFoundError, SystemRecordError, ValidationFailedError
from app.core.money import to_str
from app.modules.accounts import interface as accounts
from app.modules.documents import renderer
from app.modules.documents.core import now
from app.modules.documents.folders_rules import validate_folder_name
from app.modules.documents.models import DocTemplate
from app.modules.documents.schemas import (
    PreviewIn,
    PreviewOut,
    RenderContext,
    TemplateIn,
    TemplateOut,
    TemplateTokenOut,
    TemplateUpdateIn,
)
from app.modules.identity import interface as identity
from app.modules.operations import interface as operations
from app.modules.organization import interface as organization

TYPES = frozenset({"REPORT_DOC", "MONTHLY_FOLDER_RULE"})


async def template_outs(db: AsyncSession, items: list[DocTemplate]) -> list[TemplateOut]:
    names = {k: v.full_name for k, v in (await identity.user_briefs(db, [t.created_by for t in items])).items()}
    return [TemplateOut(id=t.id, template_type=t.template_type, name=t.name, description=t.description,
                        is_system_default=t.is_system_default, content_schema=t.content_schema,
                        created_by_name=names.get(t.created_by) if t.created_by and not t.is_system_default else None,
                        created_at=t.created_at) for t in items]  # fmt: skip


def validate_schema(template_type: str, schema: Any) -> dict[str, Any]:
    if template_type not in TYPES:
        raise ValidationFailedError("template_type must be REPORT_DOC or MONTHLY_FOLDER_RULE")
    if not isinstance(schema, dict):
        raise ValidationFailedError("content_schema must be an object")
    if template_type == "REPORT_DOC":
        blocks = schema.get("blocks")
        if not isinstance(blocks, list) or not all(
            isinstance(b, dict) and isinstance(b.get("type"), str) and isinstance(b.get("id"), str) for b in blocks
        ):
            raise ValidationFailedError("content_schema.blocks must be a list of {id, type, data} blocks")
        ids = [b["id"] for b in blocks]
        if len(set(ids)) != len(ids):
            raise ValidationFailedError("Block ids must be unique")
        return {**schema, "blocks": [{"id": b["id"], "type": b["type"], "data": b.get("data") or {}} for b in blocks]}
    custom = schema.get("custom", [])
    if not isinstance(custom, list):
        raise ValidationFailedError("content_schema.custom must be a list of folder names")
    names = []
    for item in custom:
        raw = item.get("name") if isinstance(item, dict) else item
        name = validate_folder_name(raw if isinstance(raw, str) else None)
        if name is None:
            raise ValidationFailedError(f"Invalid folder name {raw!r}")
        names.append({"name": name})
    return {**schema, "custom": names}


async def get_template(db: AsyncSession, ctx: TenantContext, tid: uuid.UUID) -> DocTemplate:
    t = await db.get(DocTemplate, tid)
    if t is None or t.org_id != ctx.org_id:
        raise NotFoundError("Template not found")
    return t


async def list_templates(db: AsyncSession, ctx: TenantContext, template_type: str | None) -> list[TemplateOut]:
    stmt = select(DocTemplate).where(DocTemplate.org_id == ctx.org_id)
    if template_type:
        stmt = stmt.where(DocTemplate.template_type == template_type)
    rows = (await db.execute(stmt.order_by(DocTemplate.is_system_default.desc(), DocTemplate.name))).scalars()
    return await template_outs(db, list(rows))


async def get_template_out(db: AsyncSession, ctx: TenantContext, tid: uuid.UUID) -> TemplateOut:
    return (await template_outs(db, [await get_template(db, ctx, tid)]))[0]


async def create_template(db: AsyncSession, ctx: TenantContext, body: TemplateIn) -> TemplateOut:
    schema = validate_schema(body.template_type, body.content_schema)
    t = DocTemplate(org_id=ctx.org_id, template_type=body.template_type, name=body.name, description=body.description,
                    is_system_default=False, content_schema=schema, created_by=ctx.user_id, created_at=now(),
                    updated_at=now())  # fmt: skip
    db.add(t)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "CREATE", "doc_template", t.id, after=t.to_dict())
    return (await template_outs(db, [t]))[0]


async def update_template(db: AsyncSession, ctx: TenantContext, tid: uuid.UUID, body: TemplateUpdateIn) -> TemplateOut:
    t = await get_template(db, ctx, tid)
    if t.is_system_default:
        raise SystemRecordError("System templates cannot be edited; clone it instead")
    before = t.to_dict()
    fields = body.model_fields_set
    if "name" in fields and body.name:
        t.name = body.name
    if "description" in fields:
        t.description = body.description
    if "content_schema" in fields and body.content_schema is not None:
        t.content_schema = validate_schema(t.template_type, body.content_schema)
    t.updated_at = now()
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "UPDATE", "doc_template", t.id, before=before, after=t.to_dict(),
                      changed_only=True)  # fmt: skip
    return (await template_outs(db, [t]))[0]


async def delete_template(db: AsyncSession, ctx: TenantContext, tid: uuid.UUID) -> None:
    t = await get_template(db, ctx, tid)
    if t.is_system_default:
        raise SystemRecordError("System templates cannot be deleted")
    before = t.to_dict()
    await db.delete(t)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "DELETE", "doc_template", tid, before=before)


async def clone_template(db: AsyncSession, ctx: TenantContext, tid: uuid.UUID) -> TemplateOut:
    src = await get_template(db, ctx, tid)
    t = DocTemplate(org_id=ctx.org_id, template_type=src.template_type, name=f"Copy of {src.name}"[:200],
                    description=src.description, is_system_default=False, content_schema=src.content_schema,
                    created_by=ctx.user_id, created_at=now(), updated_at=now())  # fmt: skip
    db.add(t)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "CREATE", "doc_template", t.id, after={"cloned_from": str(src.id)})
    return (await template_outs(db, [t]))[0]


def list_tokens() -> list[TemplateTokenOut]:
    from app.modules.documents.interface import template_tokens

    return [TemplateTokenOut(**t._asdict()) for t in template_tokens()]


# ---------------------------------------------------------------- rendering
async def _item_values(db: AsyncSession, ctx: TenantContext, item_id: uuid.UUID) -> dict:
    item = await accounts.get_stock_item(db, ctx, item_id)
    vals: dict[str, str | None] = {"item.name": item.name, "item.sku_code": item.sku_code, "item.uom": item.uom_primary,
                                   "item.hsn_sac_code": item.hsn_sac_code, "item.target_type": item.target_type}  # fmt: skip
    for k, v in (item.custom_fields or {}).items():
        vals[f"item.custom.{k}"] = None if v is None else str(v)
    return vals


async def _voucher_values(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> dict:
    v = await accounts.get_voucher(db, ctx, voucher_id)
    return {"voucher.number": v.voucher_number, "voucher.date": v.voucher_date.isoformat(),
            "voucher.type": v.voucher_type_name, "voucher.party": v.party_name, "voucher.amount": to_str(v.total_amount),
            "voucher.supplier_invoice_no": getattr(v, "supplier_invoice_no", None)}  # fmt: skip


async def render_with_context(
    db: AsyncSession, ctx: TenantContext, content: dict[str, Any], context: RenderContext | None
) -> tuple[dict[str, Any], list[str]]:
    context = context or RenderContext()
    values: dict[str, str | None] = {"today": date.today().isoformat()}
    org = await organization.get_org_brief(db, ctx.org_id)
    if org is not None:
        values.update({"org.legal_name": org.legal_name, "org.trade_name": org.mailing_name or org.legal_name,
                       "org.address": ", ".join(org.address_lines), "org.gstin": org.gstin or "", "org.pan": org.pan or "",
                       "org.phone": org.contact_phone, "org.email": org.contact_email})  # fmt: skip
    data = await operations.template_values(db, ctx, run_id=context.period_run_id, step_id=context.step_id)
    values.update(data.values)
    item_id = context.stock_item_id or data.stock_item_id
    if item_id:
        values.update(await _item_values(db, ctx, item_id))
    if context.voucher_id:
        values.update(await _voucher_values(db, ctx, context.voucher_id))
    rendered, render_warnings = renderer.render_content(content, values, qc_rows=data.qc_rows)
    return rendered, render_warnings


async def preview(db: AsyncSession, ctx: TenantContext, tid: uuid.UUID, body: PreviewIn) -> PreviewOut:
    t = await get_template(db, ctx, tid)
    if t.template_type != "REPORT_DOC":
        raise ValidationFailedError("Only report templates can be previewed")
    content, warnings = await render_with_context(db, ctx, t.content_schema, body.context)
    return PreviewOut(rich_content=content, warnings=warnings)
