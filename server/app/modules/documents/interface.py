"""Public API of the documents module (binding signatures, plan §3.6).

Implemented by S1: ``seed_org_documents``, ``ensure_month_folders`` (+ ``MonthFolders``), ``resource_names``,
``storage_used_bytes``. S4: run folders, generated files, document lookups for operations (dossier, step attachment counts).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.modules.documents import core as _core
from app.modules.documents.models import DocFolder, DocTemplate, Document
from app.modules.documents.seeding import MonthFolders, ensure_month_folders, seed_org_documents


async def resource_names(
    db: AsyncSession, ctx: TenantContext, resource_type: str, ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if resource_type != "DOC_FOLDER" or not ids:
        return {}
    rows = await db.execute(
        select(DocFolder.id, DocFolder.name).where(DocFolder.org_id == ctx.org_id, DocFolder.id.in_(ids))
    )
    return {i: n for i, n in rows.all()}


async def storage_used_bytes(db: AsyncSession, ctx: TenantContext) -> int:
    total = (
        await db.execute(select(func.coalesce(func.sum(Document.file_size), 0)).where(Document.org_id == ctx.org_id))
    ).scalar_one()
    return int(total)


# ---------------------------------------------------------------- S4 implementations
@dataclass(frozen=True, slots=True)
class DocumentDTO:
    id: uuid.UUID
    folder_id: uuid.UUID
    title: str
    source_type: str
    file_name: str | None
    file_mime_type: str | None
    file_size: int | None
    storage_key: str | None
    upload_status: str
    iso_doc_number: str | None
    revision_no: int
    approval_status: str
    linked_voucher_id: uuid.UUID | None
    linked_period_run_id: uuid.UUID | None
    linked_step_id: uuid.UUID | None
    linked_stock_item_id: uuid.UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AttachmentDTO:
    id: uuid.UUID
    title: str
    source_type: str
    file_name: str | None
    step_id: uuid.UUID | None
    step_name: str | None
    revision_no: int
    approval_status: str


def _dto(d: Document) -> DocumentDTO:
    return DocumentDTO(d.id, d.folder_id, d.title, d.source_type, d.file_name, d.file_mime_type, d.file_size,
                       d.storage_key, d.upload_status, d.iso_doc_number, d.revision_no, d.approval_status,
                       d.linked_voucher_id, d.linked_period_run_id, d.linked_step_id, d.linked_stock_item_id,
                       d.created_at)  # fmt: skip


async def create_run_folder(
    db: AsyncSession, ctx: TenantContext, *, run_id: uuid.UUID, run_title: str, month: date
) -> uuid.UUID:
    """Locked ``/FY …/MM - Month YYYY/Operations & Production Runs/<run_title>`` (idempotent per run)."""
    return await _core.create_run_folder(db, ctx, run_id=run_id, run_title=run_title, month=month)


async def store_generated_file(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    folder_id: uuid.UUID,
    title: str,
    mime: str,
    data: bytes,
    source_type: str,
    file_name: str | None = None,
    linked_voucher_id: uuid.UUID | None = None,
    linked_period_run_id: uuid.UUID | None = None,
    linked_step_id: uuid.UUID | None = None,
    linked_stock_item_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Upload bytes to storage and create a READY document row (payslips, dossiers, vouchers)."""
    return await _core.store_generated_file(
        db, ctx, folder_id=folder_id, title=title, mime=mime, data=data, source_type=source_type,
        file_name=file_name, linked_voucher_id=linked_voucher_id, linked_period_run_id=linked_period_run_id,
        linked_step_id=linked_step_id, linked_stock_item_id=linked_stock_item_id,
    )  # fmt: skip


async def get_document(db: AsyncSession, ctx: TenantContext, document_id: uuid.UUID) -> DocumentDTO:
    return _dto(await _core.get_doc(db, ctx, document_id))


async def count_documents_by_steps(
    db: AsyncSession, ctx: TenantContext, step_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not step_ids:
        return {}
    rows = await db.execute(select(Document.linked_step_id, func.count()).where(
        Document.org_id == ctx.org_id, Document.linked_step_id.in_(step_ids)).group_by(Document.linked_step_id))  # fmt: skip
    return {k: int(v) for k, v in rows.all()}


async def list_run_attachments(
    db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID, step_names: dict[uuid.UUID, str]
) -> list[AttachmentDTO]:
    """Documents linked to the run or to any of its steps (dossier appendix)."""
    conds = [Document.linked_period_run_id == run_id]
    if step_names:
        conds.append(Document.linked_step_id.in_(list(step_names)))
    rows = await db.execute(select(Document).where(Document.org_id == ctx.org_id, or_(*conds))
                            .order_by(Document.created_at))  # fmt: skip
    return [AttachmentDTO(d.id, d.title, d.source_type, d.file_name, d.linked_step_id,
                          step_names.get(d.linked_step_id) if d.linked_step_id else None, d.revision_no,
                          d.approval_status) for d in rows.scalars()]  # fmt: skip


def template_tokens() -> list[Any]:
    """Token catalogue (``token`` with braces, e.g. ``{{org.legal_name}}``) for both token endpoints."""
    from app.modules.documents.renderer import TOKEN_CATALOGUE
    from app.modules.superadmin.interface import TemplateToken

    return [TemplateToken("{{" + t + "}}", label, group, sample) for t, label, group, sample in TOKEN_CATALOGUE]


async def upsert_platform_doc_template(db: AsyncSession, ctx: TenantContext, key: str, payload: dict) -> bool:
    """Superadmin push: upsert the org's system REPORT_DOC template ``system_key=key`` (custom ones untouched)."""
    row = (await db.execute(select(DocTemplate).where(
        DocTemplate.org_id == ctx.org_id, DocTemplate.template_type == "REPORT_DOC", DocTemplate.system_key == key,
        DocTemplate.is_system_default.is_(True)))).scalar()  # fmt: skip
    if row is None:
        row = DocTemplate(org_id=ctx.org_id, template_type="REPORT_DOC", system_key=key, is_system_default=True,
                          name=payload["name"], content_schema={})  # fmt: skip
        db.add(row)
    row.name, row.description = payload["name"], payload.get("description")
    row.content_schema = {"blocks": payload["blocks"]}
    await db.flush()
    return True


async def apply_monthly_folder_rule(db: AsyncSession, ctx: TenantContext, payload: dict) -> bool:
    """Superadmin push: replace system MONTHLY_FOLDER_RULE ``subfolders``, keeping the org's ``custom`` list."""
    row = (await db.execute(select(DocTemplate).where(
        DocTemplate.org_id == ctx.org_id, DocTemplate.template_type == "MONTHLY_FOLDER_RULE",
        DocTemplate.is_system_default.is_(True)))).scalar()  # fmt: skip
    if row is None or "subfolders" not in payload:
        return False
    row.content_schema = {**(row.content_schema or {}), "subfolders": payload["subfolders"]}
    await db.flush()
    return True


async def existing_document_ids(db: AsyncSession, ctx: TenantContext, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    rows = await db.execute(select(Document.id).where(Document.org_id == ctx.org_id, Document.id.in_(ids)))
    return set(rows.scalars())


__all__ = [
    "AttachmentDTO",
    "apply_monthly_folder_rule",
    "DocumentDTO",
    "MonthFolders",
    "count_documents_by_steps",
    "create_run_folder",
    "ensure_month_folders",
    "existing_document_ids",
    "get_document",
    "list_run_attachments",
    "resource_names",
    "seed_org_documents",
    "storage_used_bytes",
    "store_generated_file",
    "template_tokens",
    "upsert_platform_doc_template",
]


async def link_document_to_voucher(
    db: AsyncSession, ctx: TenantContext, *, document_id: uuid.UUID, voucher_id: uuid.UUID
) -> None:
    """Attach a bill to a voucher: caller needs WRITE on documents.capture_upload for the document's folder."""
    from app.core.audit import write_audit
    from app.core.errors import ConflictError

    doc = await _core.get_doc(db, ctx, document_id)
    await _core.assert_folder(db, ctx, doc.folder_id, "documents.capture_upload", "WRITE")
    if doc.linked_voucher_id not in (None, voucher_id):
        raise ConflictError("This document is already attached to another voucher")
    doc.linked_voucher_id = voucher_id
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "UPDATE", "document", doc.id, after={"linked_voucher_id": str(voucher_id)})


async def list_documents_for_voucher(db: AsyncSession, ctx: TenantContext, voucher_id: uuid.UUID) -> list[DocumentDTO]:
    access = await _core.folder_access(db, ctx)
    rows = await db.execute(select(Document).where(Document.org_id == ctx.org_id, Document.linked_voucher_id == voucher_id)
                            .order_by(Document.created_at))  # fmt: skip
    return [_dto(d) for d in rows.scalars() if access.visible(d.folder_id)]
