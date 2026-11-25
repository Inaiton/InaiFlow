"""Documents: list/search, uploads (signed tickets), internal documents from templates, edit/delete,
signed downloads, PDF/DOCX export, ISO 7.5 lifecycle (review/approve/obsolete, segregation of duties),
revisions and audit trail."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.export import Letterhead, Report, get_exporter
from app.adapters.storage import build_org_key, get_storage, validate_upload
from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import (
    DocumentLockedError,
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
    SegregationOfDutiesError,
    UploadIncompleteError,
    ValidationFailedError,
)
from app.core.pagination import PageParams, paginate
from app.core.schemas import AuditLogOut, SignedUrlOut, UploadTicket
from app.modules.documents.core import EXPLORER, assert_folder, folder_access, folder_path, get_doc, now
from app.modules.documents.models import Document
from app.modules.documents.schemas import (
    CompleteUploadIn,
    DocCreateIn,
    DocumentOut,
    DocumentSummary,
    DocUpdateIn,
    DocUploadIn,
    DocUploadOut,
    ReviewIn,
    ReviseIn,
    ReviseOut,
    SearchHit,
    TransitionIn,
)
from app.modules.documents.service_templates import get_template, render_with_context
from app.modules.identity import interface as identity
from app.modules.operations import interface as operations
from app.modules.organization import interface as organization

CAPTURE, EDITOR, APPROVAL = "documents.capture_upload", "documents.editor", "documents.iso_approval"
UPLOAD_SOURCES = frozenset({"FILE_UPLOAD", "CAMERA_SCAN"})
INTERNAL_SOURCES = frozenset({"INTERNAL_TEMPLATE", "BLANK_ADHOC"})


# ---------------------------------------------------------------- outs
async def _names(db: AsyncSession, ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    return {k: v.full_name for k, v in (await identity.user_briefs(db, [i for i in ids if i])).items()}


def _summary(d: Document, names: dict[uuid.UUID, str]) -> DocumentSummary:
    return DocumentSummary(id=d.id, folder_id=d.folder_id, title=d.title, source_type=d.source_type,
                           file_name=d.file_name, file_mime_type=d.file_mime_type, file_size=d.file_size,
                           upload_status=d.upload_status, iso_doc_number=d.iso_doc_number, revision_no=d.revision_no,
                           approval_status=d.approval_status, linked_voucher_id=d.linked_voucher_id,
                           linked_period_run_id=d.linked_period_run_id, linked_step_id=d.linked_step_id,
                           linked_stock_item_id=d.linked_stock_item_id, prepared_by_name=names.get(d.prepared_by, ""),
                           created_at=d.created_at, updated_at=d.updated_at)  # fmt: skip


async def summaries(db: AsyncSession, docs: list[Document]) -> list[DocumentSummary]:
    names = await _names(db, [d.prepared_by for d in docs])
    return [_summary(d, names) for d in docs]


def deletable(d: Document) -> bool:
    return d.approval_status not in ("APPROVED", "OBSOLETE") and not d.linked_voucher_id and not d.linked_step_id


async def document_out(db: AsyncSession, ctx: TenantContext, d: Document) -> DocumentOut:
    await db.flush()
    await db.refresh(d)
    names = await _names(db, [d.prepared_by, d.reviewed_by, d.approved_by])
    path = [f.name for f in await folder_path(db, ctx, d.folder_id)]
    return DocumentOut(**_summary(d, names).model_dump(), rich_content=d.rich_content, template_id=d.template_id,
                       ocr_text=d.ocr_text, reviewed_by_name=names.get(d.reviewed_by) if d.reviewed_by else None,
                       review_comment=d.review_comment,
                       approved_by_name=names.get(d.approved_by) if d.approved_by else None,
                       approved_at=d.approved_at, previous_revision_id=d.previous_revision_id, folder_path=path,
                       can_delete=deletable(d) and ctx.has(EXPLORER, "FULL"))  # fmt: skip


async def _visible_doc(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID, key: str = EXPLORER,
                       level: str = "READ") -> Document:  # fmt: skip
    d = await get_doc(db, ctx, doc_id)
    await assert_folder(db, ctx, d.folder_id, key, level)
    return d


# ---------------------------------------------------------------- list & search
async def _visible_folder_ids(db: AsyncSession, ctx: TenantContext) -> list[uuid.UUID] | None:
    access = await folder_access(db, ctx)
    if ctx.is_owner or not access.overrides:
        return None
    return [fid for fid in access.parents if access.visible(fid)]


async def _acl_where(db: AsyncSession, ctx: TenantContext, stmt: Select[Any]) -> Select[Any]:
    visible = await _visible_folder_ids(db, ctx)
    return stmt.where(Document.folder_id.in_(visible)) if visible is not None else stmt


async def list_documents(
    db: AsyncSession, ctx: TenantContext, page: PageParams, **f: Any
) -> tuple[list[DocumentSummary], int]:
    stmt = select(Document).where(Document.org_id == ctx.org_id)
    if f.get("folder_id"):
        await assert_folder(db, ctx, f["folder_id"])
        stmt = stmt.where(Document.folder_id == f["folder_id"])
    for col in (
        "source_type",
        "approval_status",
        "linked_period_run_id",
        "linked_step_id",
        "linked_voucher_id",
        "linked_stock_item_id",
    ):
        if f.get(col) is not None:
            stmt = stmt.where(getattr(Document, col) == f[col])
    if f.get("iso_only"):
        stmt = stmt.where(Document.iso_doc_number.is_not(None))
    if f.get("q"):
        like = f"%{f['q'].strip()}%"
        stmt = stmt.where(or_(Document.title.ilike(like), Document.file_name.ilike(like),
                              Document.iso_doc_number.ilike(like)))  # fmt: skip
    stmt = await _acl_where(db, ctx, stmt)
    rows, total = await paginate(db, stmt.order_by(Document.created_at.desc()), page)
    return await summaries(db, [r[0] for r in rows]), total


async def search(db: AsyncSession, ctx: TenantContext, q: str, limit: int) -> list[SearchHit]:
    q = (q or "").strip()
    if not q:
        raise ValidationFailedError("q is required")
    tsq = func.plainto_tsquery("simple", q)
    like = f"%{q}%"
    rank = func.ts_rank(Document.search_tsv, tsq)
    snippet = func.ts_headline("simple", func.coalesce(Document.ocr_text, "") + " " + Document.title, tsq,
                               "MaxWords=18, MinWords=6, StartSel=<<, StopSel=>>")  # fmt: skip
    stmt = select(Document, snippet).where(
        Document.org_id == ctx.org_id, Document.upload_status == "READY",
        or_(Document.search_tsv.op("@@")(tsq), Document.title.ilike(like), Document.file_name.ilike(like),
            Document.iso_doc_number.ilike(like), Document.ocr_text.ilike(like)))  # fmt: skip
    stmt = await _acl_where(db, ctx, stmt)
    rows = (
        await db.execute(stmt.order_by(rank.desc(), Document.created_at.desc()).limit(min(max(limit, 1), 200)))
    ).all()
    docs = [r[0] for r in rows]
    sums = await summaries(db, docs)
    hits = []
    for s, (d, snip) in zip(sums, rows, strict=True):
        path = [f.name for f in await folder_path(db, ctx, d.folder_id)]
        hits.append(SearchHit(document=s, snippet=(snip or "").strip() or None, folder_path=path))
    return hits


# ---------------------------------------------------------------- links
async def _check_links(
    db: AsyncSession, ctx: TenantContext, run_id: uuid.UUID | None, step_id: uuid.UUID | None
) -> uuid.UUID | None:
    if step_id:
        owner = (await operations.step_run_ids(db, ctx, [step_id])).get(step_id)
        if owner is None or (run_id and owner != run_id):
            raise NotFoundError("Step not found")
        run_id = run_id or owner
    if run_id and not await operations.get_runs_by_ids(db, ctx, [run_id]):
        raise NotFoundError("Run not found")
    return run_id


# ---------------------------------------------------------------- uploads
async def upload_url(db: AsyncSession, ctx: TenantContext, body: DocUploadIn) -> DocUploadOut:
    folder = await assert_folder(db, ctx, body.folder_id, CAPTURE, "WRITE")
    source = body.source_type or "FILE_UPLOAD"
    if source not in UPLOAD_SOURCES:
        raise ValidationFailedError("source_type must be FILE_UPLOAD or CAMERA_SCAN for uploads")
    validate_upload(body.content_type, body.size_bytes)
    run_id = await _check_links(db, ctx, body.linked_period_run_id, body.linked_step_id)
    key = build_org_key(ctx.org_id, body.file_name)
    ticket = await get_storage().create_upload_ticket(key, body.content_type, body.size_bytes)
    d = Document(org_id=ctx.org_id, folder_id=folder.id, title=body.title, source_type=source, file_name=body.file_name,
                 file_mime_type=body.content_type.split(";")[0].strip().lower(), file_size=body.size_bytes,
                 storage_key=key, upload_status="PENDING", iso_doc_number=body.iso_doc_number or None,
                 linked_voucher_id=body.linked_voucher_id, linked_period_run_id=run_id,
                 linked_step_id=body.linked_step_id, linked_stock_item_id=body.linked_stock_item_id,
                 prepared_by=ctx.user_id, approval_status="DRAFT", revision_no=1, created_at=now(), updated_at=now())  # fmt: skip
    db.add(d)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "CREATE", "document", d.id,
                      after={"title": d.title, "file_name": d.file_name, "folder_id": folder.id})  # fmt: skip
    return DocUploadOut(document=await document_out(db, ctx, d), upload=_ticket(ticket))


def _ticket(t: Any) -> UploadTicket:
    return UploadTicket(upload_url=t.upload_url, method=t.method, headers=t.headers, storage_key=t.storage_key,
                        expires_at=t.expires_at)  # fmt: skip


async def complete_upload(
    db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID, body: CompleteUploadIn
) -> DocumentOut:
    d = await _visible_doc(db, ctx, doc_id, CAPTURE, "WRITE")
    if d.upload_status == "READY":
        return await document_out(db, ctx, d)
    if not d.storage_key:
        raise InvalidStateError("This document has no file")
    info = await get_storage().head(d.storage_key)
    if info is None:
        raise UploadIncompleteError()
    if d.file_size is not None and info.size != d.file_size:
        raise UploadIncompleteError("The uploaded size does not match", {"expected": d.file_size, "actual": info.size})
    if body.checksum_sha256 is not None and len(body.checksum_sha256) != 64:
        raise ValidationFailedError("checksum_sha256 must be 64 hex characters")
    d.upload_status, d.checksum_sha256, d.updated_at = "READY", body.checksum_sha256, now()
    if body.ocr_text is not None:
        d.ocr_text = body.ocr_text[:200_000]
    await write_audit(db, ctx, "DOCUMENTS", "UPDATE", "document", d.id, after={"upload_status": "READY"})
    return await document_out(db, ctx, d)


# ---------------------------------------------------------------- internal documents
async def create_document(db: AsyncSession, ctx: TenantContext, body: DocCreateIn) -> DocumentOut:
    folder = await assert_folder(db, ctx, body.folder_id, EDITOR, "WRITE")
    if body.source_type not in INTERNAL_SOURCES:
        raise ValidationFailedError("source_type must be INTERNAL_TEMPLATE or BLANK_ADHOC")
    run_id = await _check_links(db, ctx, body.linked_period_run_id or (body.context.period_run_id if body.context else None),
                                body.linked_step_id or (body.context.step_id if body.context else None))  # fmt: skip
    content: dict[str, Any] = body.rich_content.model_dump(mode="json") if body.rich_content else {"blocks": []}
    template_id = None
    if body.template_id:
        t = await get_template(db, ctx, body.template_id)
        if t.template_type != "REPORT_DOC":
            raise ValidationFailedError("Only report templates can create documents")
        content, _warnings = await render_with_context(db, ctx, t.content_schema, body.context)
        template_id = t.id
    elif body.source_type == "INTERNAL_TEMPLATE":
        raise ValidationFailedError("template_id is required for INTERNAL_TEMPLATE documents")
    step_id = body.linked_step_id or (body.context.step_id if body.context else None)
    d = Document(org_id=ctx.org_id, folder_id=folder.id, title=body.title, source_type=body.source_type,
                 upload_status="READY", rich_content=content, template_id=template_id,
                 iso_doc_number=body.iso_doc_number or None, linked_voucher_id=body.linked_voucher_id,
                 linked_period_run_id=run_id, linked_step_id=step_id,
                 linked_stock_item_id=body.linked_stock_item_id or (body.context.stock_item_id if body.context else None),
                 prepared_by=ctx.user_id, approval_status="DRAFT", revision_no=1, created_at=now(), updated_at=now())  # fmt: skip
    db.add(d)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "CREATE", "document", d.id,
                      after={"title": d.title, "source_type": d.source_type, "template_id": template_id})  # fmt: skip
    return await document_out(db, ctx, d)


async def get_document_out(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID) -> DocumentOut:
    return await document_out(db, ctx, await _visible_doc(db, ctx, doc_id))


async def update_document(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID, body: DocUpdateIn) -> DocumentOut:
    d = await _visible_doc(db, ctx, doc_id, EDITOR, "WRITE")
    before = d.to_dict()
    fields = body.model_fields_set
    if ("rich_content" in fields or "iso_doc_number" in fields) and d.approval_status != "DRAFT":
        raise DocumentLockedError("Only draft documents can be edited; create a revision")
    if "rich_content" in fields:
        if d.source_type not in INTERNAL_SOURCES:
            raise ValidationFailedError("Uploaded files have no editable content")
        d.rich_content = body.rich_content.model_dump(mode="json") if body.rich_content else {"blocks": []}
    if "iso_doc_number" in fields:
        d.iso_doc_number = body.iso_doc_number or None
    if "title" in fields and body.title:
        d.title = body.title
    if "folder_id" in fields and body.folder_id and body.folder_id != d.folder_id:
        await assert_folder(db, ctx, body.folder_id, CAPTURE, "WRITE")
        d.folder_id = body.folder_id
    d.updated_at = now()
    await db.flush()
    await db.refresh(d)  # search_tsv is regenerated by the database
    await write_audit(db, ctx, "DOCUMENTS", "UPDATE", "document", d.id, before=before, after=d.to_dict(),
                      changed_only=True)  # fmt: skip
    return await document_out(db, ctx, d)


async def delete_document(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID) -> None:
    d = await _visible_doc(db, ctx, doc_id, EXPLORER, "FULL")
    if not deletable(d):
        raise DocumentLockedError(
            "Approved/obsolete documents and documents linked to vouchers or steps cannot be deleted"
        )
    key = d.storage_key
    shared = key and (await db.execute(select(func.count()).where(
        Document.org_id == ctx.org_id, Document.storage_key == key, Document.id != d.id))).scalar_one()  # fmt: skip
    await db.execute(update(Document).where(Document.previous_revision_id == d.id).values(previous_revision_id=None))
    before = d.to_dict()
    await db.delete(d)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "DELETE", "document", doc_id, before=before)
    if key and not shared:
        await get_storage().delete(key)


async def download_url(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID) -> SignedUrlOut:
    d = await _visible_doc(db, ctx, doc_id)
    if d.upload_status != "READY" or not d.storage_key:
        raise UploadIncompleteError("This document has no downloadable file")
    url = await get_storage().create_download_url(d.storage_key, filename=d.file_name)
    return SignedUrlOut(url=url.url, expires_at=url.expires_at)


async def export(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID, fmt: str) -> tuple[bytes, str, str]:
    d = await _visible_doc(db, ctx, doc_id)
    fmt = (fmt or "").lower()
    if fmt not in ("pdf", "docx"):
        raise ValidationFailedError("format must be pdf or docx")
    if d.source_type not in INTERNAL_SOURCES or d.rich_content is None:
        raise ValidationFailedError("Only internal documents can be exported; download the file instead")
    org = await organization.get_org_brief(db, ctx.org_id)
    names = await _names(db, [d.prepared_by, d.reviewed_by, d.approved_by])
    blocks = list((d.rich_content or {}).get("blocks") or [])
    stamp = [{"label": "Document no.", "value": d.iso_doc_number or "-"}, {"label": "Revision", "value": str(d.revision_no)},
             {"label": "Status", "value": d.approval_status},
             {"label": "Prepared by", "value": names.get(d.prepared_by, "")},
             {"label": "Reviewed by", "value": names.get(d.reviewed_by, "") if d.reviewed_by else "-"},
             {"label": "Approved by", "value": (f"{names.get(d.approved_by, '')} on {d.approved_at:%Y-%m-%d}"
                                                if d.approved_by and d.approved_at else "-")}]  # fmt: skip
    blocks += [{"type": "divider", "data": {}}, {"type": "kv", "data": {"rows": stamp}}]
    report = Report(title=d.title, blocks=blocks, watermark="OBSOLETE" if d.approval_status == "OBSOLETE" else None,
                    letterhead=Letterhead(name=org.legal_name, lines=org.address_lines[:2]) if org else None,
                    footer=f"{d.iso_doc_number or d.title} · Rev {d.revision_no}")  # fmt: skip
    exporter = get_exporter()
    await write_audit(db, ctx, "DOCUMENTS", "EXPORT", "document", d.id, after={"format": fmt})
    return exporter.render(report, fmt), exporter.mime(fmt), f"{d.title}.{fmt}"


# ---------------------------------------------------------------- ISO 7.5 lifecycle
async def _audit_transition(
    db: AsyncSession, ctx: TenantContext, d: Document, before: str, comment: str | None
) -> None:
    await write_audit(db, ctx, "DOCUMENTS", "TRANSITION", "document", d.id, before={"approval_status": before},
                      after={"approval_status": d.approval_status, "revision_no": d.revision_no}, reason=comment)  # fmt: skip


def _require(ctx: TenantContext, key: str, level: str) -> None:
    if not ctx.has(key, level):
        raise PermissionDeniedError(details={"permission": key, "required": level})


async def transition(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID, body: TransitionIn) -> DocumentOut:
    d = await _visible_doc(db, ctx, doc_id, EDITOR, "WRITE")
    cur, to = d.approval_status, body.to
    if cur == "DRAFT" and to == "UNDER_REVIEW":
        if d.upload_status != "READY":
            raise UploadIncompleteError("Finish the upload before submitting for review")
        d.reviewed_by, d.review_comment = None, None
    elif cur == "UNDER_REVIEW" and to == "DRAFT":
        _require(ctx, APPROVAL, "WRITE")
        if not (body.comment or "").strip():
            raise ValidationFailedError("A comment is required to send a document back")
        d.review_comment, d.reviewed_by = body.comment, None
    elif cur == "UNDER_REVIEW" and to == "APPROVED":
        _require(ctx, APPROVAL, "FULL")
        if d.prepared_by == ctx.user_id:
            raise SegregationOfDutiesError("The preparer cannot approve their own document")
        if d.reviewed_by is None:
            raise InvalidStateError("The document must be reviewed before approval")
        d.approved_by, d.approved_at = ctx.user_id, now()
        if body.comment:
            d.review_comment = body.comment
        await _obsolete_prior(db, ctx, d)
    elif cur == "APPROVED" and to == "OBSOLETE":
        _require(ctx, APPROVAL, "FULL")
    else:
        raise InvalidStateError(f"Cannot move a document from {cur} to {to}")
    d.approval_status, d.updated_at = to, now()
    await db.flush()
    await _audit_transition(db, ctx, d, cur, body.comment)
    return await document_out(db, ctx, d)


async def _obsolete_prior(db: AsyncSession, ctx: TenantContext, d: Document) -> None:
    chain = {x.id for x in await _chain(db, ctx, d)}
    conds = [Document.id.in_(chain)]
    if d.iso_doc_number:
        conds.append(Document.iso_doc_number == d.iso_doc_number)
    priors = list((await db.execute(select(Document).where(
        Document.org_id == ctx.org_id, Document.id != d.id, Document.approval_status == "APPROVED",
        or_(*conds)).with_for_update())).scalars())  # fmt: skip
    for p in priors:
        p.approval_status, p.updated_at = "OBSOLETE", now()
        await _audit_transition(db, ctx, p, "APPROVED", f"Superseded by revision {d.revision_no}")


async def review(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID, body: ReviewIn) -> DocumentOut:
    d = await _visible_doc(db, ctx, doc_id)
    if d.approval_status != "UNDER_REVIEW":
        raise InvalidStateError("Only documents under review can be reviewed")
    if d.prepared_by == ctx.user_id:
        raise SegregationOfDutiesError("The preparer cannot review their own document")
    d.reviewed_by, d.review_comment, d.updated_at = ctx.user_id, body.comment, now()
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "APPROVE", "document", d.id, after={"reviewed_by": ctx.user_id},
                      reason=body.comment)  # fmt: skip
    return await document_out(db, ctx, d)


async def _chain(db: AsyncSession, ctx: TenantContext, d: Document) -> list[Document]:
    """All revisions of ``d``: previous_revision links both ways, plus same iso_doc_number."""
    seen: dict[uuid.UUID, Document] = {d.id: d}
    cur = d
    while cur.previous_revision_id and cur.previous_revision_id not in seen:
        prev = await db.get(Document, cur.previous_revision_id)
        if prev is None or prev.org_id != ctx.org_id:
            break
        seen[prev.id] = cur = prev
    frontier = set(seen)
    while frontier:
        nxt = list((await db.execute(select(Document).where(Document.org_id == ctx.org_id,
                                                            Document.previous_revision_id.in_(frontier)))).scalars())  # fmt: skip
        frontier = {x.id for x in nxt if x.id not in seen}
        seen.update({x.id: x for x in nxt})
    if d.iso_doc_number:
        for x in (await db.execute(select(Document).where(Document.org_id == ctx.org_id,
                                                          Document.iso_doc_number == d.iso_doc_number))).scalars():  # fmt: skip
            seen.setdefault(x.id, x)
    return sorted(seen.values(), key=lambda x: (x.revision_no, x.created_at))


async def revise(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID, body: ReviseIn) -> ReviseOut:
    src = await _visible_doc(db, ctx, doc_id, EDITOR, "WRITE")
    if src.approval_status != "APPROVED":
        raise InvalidStateError("Only approved documents can be revised")
    chain = await _chain(db, ctx, src)
    if any(x.approval_status in ("DRAFT", "UNDER_REVIEW") for x in chain):
        raise InvalidStateError("A newer revision is already in progress")
    d = Document(org_id=ctx.org_id, folder_id=src.folder_id, title=src.title, source_type=src.source_type,
                 file_name=src.file_name, file_mime_type=src.file_mime_type, file_size=src.file_size,
                 checksum_sha256=src.checksum_sha256, storage_key=src.storage_key, upload_status=src.upload_status,
                 rich_content=src.rich_content, ocr_text=src.ocr_text, template_id=src.template_id,
                 iso_doc_number=src.iso_doc_number, revision_no=max(x.revision_no for x in chain) + 1,
                 previous_revision_id=src.id, approval_status="DRAFT", linked_voucher_id=src.linked_voucher_id,
                 linked_period_run_id=src.linked_period_run_id, linked_step_id=src.linked_step_id,
                 linked_stock_item_id=src.linked_stock_item_id, prepared_by=ctx.user_id, created_at=now(),
                 updated_at=now())  # fmt: skip
    ticket = None
    if body.file is not None:
        validate_upload(body.file.content_type, body.file.size_bytes)
        key = build_org_key(ctx.org_id, body.file.file_name)
        ticket = _ticket(await get_storage().create_upload_ticket(key, body.file.content_type, body.file.size_bytes))
        d.file_name, d.file_mime_type, d.file_size = body.file.file_name, body.file.content_type, body.file.size_bytes
        d.storage_key, d.upload_status, d.checksum_sha256, d.ocr_text = key, "PENDING", None, None
        if d.source_type in INTERNAL_SOURCES:
            d.source_type = "FILE_UPLOAD"
    db.add(d)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "CREATE", "document", d.id,
                      after={"revision_no": d.revision_no, "previous_revision_id": src.id})  # fmt: skip
    return ReviseOut(document=await document_out(db, ctx, d), upload=ticket)


async def versions(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID) -> list[DocumentSummary]:
    d = await _visible_doc(db, ctx, doc_id)
    return await summaries(db, list(reversed(await _chain(db, ctx, d))))


async def audit(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID) -> list[AuditLogOut]:
    d = await _visible_doc(db, ctx, doc_id)
    rows = (await db.execute(text(
        "SELECT id, module, action, entity_type, entity_id, actor_type, user_id, role_code, before_diff, after_diff, "
        "reason, host(ip_address) AS ip_address, created_at FROM org_audit_logs WHERE org_id = :org "
        "AND entity_id = :eid ORDER BY created_at DESC LIMIT 500"), {"org": ctx.org_id, "eid": d.id})).mappings().all()  # fmt: skip
    names = await _names(db, [r["user_id"] for r in rows])
    return [AuditLogOut(**dict(r), user_name=names.get(r["user_id"]) if r["user_id"] else None) for r in rows]
