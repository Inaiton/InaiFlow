"""Documents routes (contract section ``documents``). Static paths are registered before ``/{document_id}``."""

from __future__ import annotations

import uuid
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.context import TenantContext
from app.core.deps import TenantDB, require
from app.core.idempotency import Idem
from app.core.pagination import Page, Paging
from app.core.schemas import AuditLogOut, SignedUrlOut
from app.modules.documents import service_documents as docs
from app.modules.documents import service_folders as folders
from app.modules.documents import service_templates as templates
from app.modules.documents.schemas import (
    ApprovalStatus,
    CompleteUploadIn,
    DocCreateIn,
    DocumentOut,
    DocumentSummary,
    DocUpdateIn,
    DocUploadIn,
    DocUploadOut,
    EnsureMonthIn,
    FolderIn,
    FolderOut,
    FolderUpdateIn,
    PreviewIn,
    PreviewOut,
    ReviewIn,
    ReviseIn,
    ReviseOut,
    SearchHit,
    TemplateIn,
    TemplateOut,
    TemplateTokenOut,
    TemplateUpdateIn,
    TransitionIn,
)

router = APIRouter(tags=["documents"])
NO_CONTENT, CREATED = status.HTTP_204_NO_CONTENT, status.HTTP_201_CREATED
FILE_RESPONSES: dict[int | str, dict[str, Any]] = {200: {"content": {
    "application/pdf": {}, "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}}}}  # fmt: skip


def _g(key: str, level: str, acl: str | None = "DOC_FOLDER") -> Any:
    return Annotated[TenantContext, Depends(require(f"documents.{key}", level, acl_resource=acl))]


ExplRead, ExplFull = _g("explorer", "READ"), _g("explorer", "FULL")
CapWrite = _g("capture_upload", "WRITE")
EdWrite = _g("editor", "WRITE")
ApprWrite = _g("iso_approval", "WRITE", None)
TplRead, TplWrite, TplFull = (_g("templates", lvl, None) for lvl in ("READ", "WRITE", "FULL"))


def _file(data: bytes, mime: str, name: str) -> Response:
    return Response(content=data, media_type=mime,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})  # fmt: skip


# ---------------------------------------------------------------- folders
@router.get("/documents/folders", response_model=list[FolderOut])
async def list_folders(ctx: ExplRead, db: TenantDB, parent_id: uuid.UUID | None = None) -> list[FolderOut]:
    return await folders.list_folders(db, ctx, parent_id)


@router.post("/documents/folders", response_model=FolderOut, status_code=CREATED)
async def create_folder(body: FolderIn, ctx: CapWrite, db: TenantDB) -> FolderOut:
    return await folders.create_folder(db, ctx, body)


@router.post("/documents/folders/ensure-month", response_model=list[FolderOut])
async def ensure_month(body: EnsureMonthIn, ctx: TplFull, db: TenantDB) -> list[FolderOut]:
    return await folders.ensure_month(db, ctx, body)


@router.get("/documents/folders/{folder_id}", response_model=FolderOut)
async def get_folder(folder_id: uuid.UUID, ctx: ExplRead, db: TenantDB) -> FolderOut:
    return await folders.get_folder_out(db, ctx, folder_id)


@router.get("/documents/folders/{folder_id}/path", response_model=list[FolderOut])
async def folder_path(folder_id: uuid.UUID, ctx: ExplRead, db: TenantDB) -> list[FolderOut]:
    return await folders.get_path(db, ctx, folder_id)


@router.patch("/documents/folders/{folder_id}", response_model=FolderOut)
async def update_folder(folder_id: uuid.UUID, body: FolderUpdateIn, ctx: CapWrite, db: TenantDB) -> FolderOut:
    return await folders.update_folder(db, ctx, folder_id, body)


@router.delete("/documents/folders/{folder_id}", status_code=NO_CONTENT)
async def delete_folder(folder_id: uuid.UUID, ctx: ExplFull, db: TenantDB) -> Response:
    await folders.delete_folder(db, ctx, folder_id)
    return Response(status_code=NO_CONTENT)


# ---------------------------------------------------------------- templates (static paths first)
@router.get("/documents/template-tokens", response_model=list[TemplateTokenOut])
async def template_tokens(ctx: TplRead) -> list[TemplateTokenOut]:
    return templates.list_tokens()


@router.get("/documents/templates", response_model=list[TemplateOut])
async def list_templates(ctx: TplRead, db: TenantDB, template_type: str | None = None) -> list[TemplateOut]:
    return await templates.list_templates(db, ctx, template_type)


@router.post("/documents/templates", response_model=TemplateOut, status_code=CREATED)
async def create_template(body: TemplateIn, ctx: TplWrite, db: TenantDB) -> TemplateOut:
    return await templates.create_template(db, ctx, body)


@router.get("/documents/templates/{template_id}", response_model=TemplateOut)
async def get_template(template_id: uuid.UUID, ctx: TplRead, db: TenantDB) -> TemplateOut:
    return await templates.get_template_out(db, ctx, template_id)


@router.patch("/documents/templates/{template_id}", response_model=TemplateOut)
async def update_template(template_id: uuid.UUID, body: TemplateUpdateIn, ctx: TplWrite, db: TenantDB) -> TemplateOut:
    return await templates.update_template(db, ctx, template_id, body)


@router.delete("/documents/templates/{template_id}", status_code=NO_CONTENT)
async def delete_template(template_id: uuid.UUID, ctx: TplFull, db: TenantDB) -> Response:
    await templates.delete_template(db, ctx, template_id)
    return Response(status_code=NO_CONTENT)


@router.post("/documents/templates/{template_id}/clone", response_model=TemplateOut, status_code=CREATED)
async def clone_template(template_id: uuid.UUID, ctx: TplWrite, db: TenantDB) -> TemplateOut:
    return await templates.clone_template(db, ctx, template_id)


@router.post("/documents/templates/{template_id}/preview", response_model=PreviewOut)
async def preview_template(template_id: uuid.UUID, body: PreviewIn, ctx: TplRead, db: TenantDB) -> PreviewOut:
    return await templates.preview(db, ctx, template_id, body)


# ---------------------------------------------------------------- documents
@router.get("/documents", response_model=Page[DocumentSummary])
async def list_documents(
    ctx: ExplRead, db: TenantDB, page: Paging, folder_id: uuid.UUID | None = None, q: str | None = None,
    source_type: str | None = None, approval_status: ApprovalStatus | None = None,
    linked_period_run_id: uuid.UUID | None = None, linked_step_id: uuid.UUID | None = None,
    linked_voucher_id: uuid.UUID | None = None, linked_stock_item_id: uuid.UUID | None = None,
    iso_only: bool = False,
) -> Page[DocumentSummary]:  # fmt: skip
    items, total = await docs.list_documents(
        db, ctx, page, folder_id=folder_id, q=q, source_type=source_type, approval_status=approval_status,
        linked_period_run_id=linked_period_run_id, linked_step_id=linked_step_id,
        linked_voucher_id=linked_voucher_id, linked_stock_item_id=linked_stock_item_id, iso_only=iso_only,
    )  # fmt: skip
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/documents/search", response_model=list[SearchHit])
async def search(
    ctx: ExplRead, db: TenantDB, q: str = Query(), limit: int = Query(20, ge=1, le=200)
) -> list[SearchHit]:
    return await docs.search(db, ctx, q, limit)


@router.post("/documents/upload-url", response_model=DocUploadOut, status_code=CREATED)
async def upload_url(body: DocUploadIn, ctx: CapWrite, db: TenantDB, idem: Idem) -> DocUploadOut:
    return await idem.save(await docs.upload_url(db, ctx, body), 201)


@router.post("/documents", response_model=DocumentOut, status_code=CREATED)
async def create_document(body: DocCreateIn, ctx: EdWrite, db: TenantDB) -> DocumentOut:
    return await docs.create_document(db, ctx, body)


@router.post("/documents/{document_id}/complete-upload", response_model=DocumentOut)
async def complete_upload(document_id: uuid.UUID, body: CompleteUploadIn, ctx: CapWrite, db: TenantDB) -> DocumentOut:
    return await docs.complete_upload(db, ctx, document_id, body)


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: uuid.UUID, ctx: ExplRead, db: TenantDB) -> DocumentOut:
    return await docs.get_document_out(db, ctx, document_id)


@router.patch("/documents/{document_id}", response_model=DocumentOut)
async def update_document(document_id: uuid.UUID, body: DocUpdateIn, ctx: EdWrite, db: TenantDB) -> DocumentOut:
    return await docs.update_document(db, ctx, document_id, body)


@router.delete("/documents/{document_id}", status_code=NO_CONTENT)
async def delete_document(document_id: uuid.UUID, ctx: ExplFull, db: TenantDB) -> Response:
    await docs.delete_document(db, ctx, document_id)
    return Response(status_code=NO_CONTENT)


@router.get("/documents/{document_id}/download-url", response_model=SignedUrlOut)
async def download_url(document_id: uuid.UUID, ctx: ExplRead, db: TenantDB) -> SignedUrlOut:
    return await docs.download_url(db, ctx, document_id)


@router.get("/documents/{document_id}/export", response_class=Response, responses=FILE_RESPONSES)
async def export_document(document_id: uuid.UUID, ctx: ExplRead, db: TenantDB, format: str = Query()) -> Response:  # noqa: A002
    return _file(*await docs.export(db, ctx, document_id, format))


@router.post("/documents/{document_id}/transition", response_model=DocumentOut)
async def transition(document_id: uuid.UUID, body: TransitionIn, ctx: EdWrite, db: TenantDB) -> DocumentOut:
    return await docs.transition(db, ctx, document_id, body)


@router.post("/documents/{document_id}/review", response_model=DocumentOut)
async def review(document_id: uuid.UUID, body: ReviewIn, ctx: ApprWrite, db: TenantDB) -> DocumentOut:
    return await docs.review(db, ctx, document_id, body)


@router.post("/documents/{document_id}/revise", response_model=ReviseOut, status_code=CREATED)
async def revise(document_id: uuid.UUID, body: ReviseIn, ctx: EdWrite, db: TenantDB) -> ReviseOut:
    return await docs.revise(db, ctx, document_id, body)


@router.get("/documents/{document_id}/versions", response_model=list[DocumentSummary])
async def versions(document_id: uuid.UUID, ctx: ExplRead, db: TenantDB) -> list[DocumentSummary]:
    return await docs.versions(db, ctx, document_id)


@router.get("/documents/{document_id}/audit", response_model=list[AuditLogOut])
async def document_audit(document_id: uuid.UUID, ctx: ExplRead, db: TenantDB) -> list[AuditLogOut]:
    return await docs.audit(db, ctx, document_id)
