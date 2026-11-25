"""Folder tree: list (ACL-filtered), get, path, create, rename/move, delete, ensure-month."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import TenantContext
from app.core.errors import (
    AlreadyExistsError,
    ConflictError,
    FolderLockedError,
    FolderNotEmptyError,
    ValidationFailedError,
)
from app.modules.documents.core import (
    assert_folder,
    folder_access,
    folder_path,
    get_folder,
    now,
    parent_map,
    walker,
)
from app.modules.documents.folders_rules import validate_folder_name, would_create_cycle
from app.modules.documents.models import DocFolder, Document
from app.modules.documents.schemas import EnsureMonthIn, FolderIn, FolderOut, FolderUpdateIn
from app.modules.documents.seeding import ensure_month_folders

CAPTURE = "documents.capture_upload"


async def folder_outs(db: AsyncSession, folders: list[DocFolder]) -> list[FolderOut]:
    if not folders:
        return []
    ids = [f.id for f in folders]
    children = dict((await db.execute(select(DocFolder.parent_folder_id, func.count()).where(
        DocFolder.parent_folder_id.in_(ids)).group_by(DocFolder.parent_folder_id))).all())  # fmt: skip
    docs = dict((await db.execute(select(Document.folder_id, func.count()).where(
        Document.folder_id.in_(ids)).group_by(Document.folder_id))).all())  # fmt: skip
    return [FolderOut(id=f.id, parent_folder_id=f.parent_folder_id, name=f.name, system_kind=f.system_kind,
                      fy_label=f.fy_label, month_date=f.month_date, is_system_locked=f.is_system_locked,
                      linked_period_run_id=f.linked_period_run_id, child_count=int(children.get(f.id, 0)),
                      document_count=int(docs.get(f.id, 0)), created_at=f.created_at) for f in folders]  # fmt: skip


def _order(stmt):  # noqa: ANN001,ANN202
    return stmt.order_by(DocFolder.month_date.desc().nulls_first(), DocFolder.name)


async def list_folders(db: AsyncSession, ctx: TenantContext, parent_id: uuid.UUID | None) -> list[FolderOut]:
    access = await folder_access(db, ctx)
    if parent_id is not None:
        await assert_folder(db, ctx, parent_id)
        rows = (await db.execute(_order(select(DocFolder).where(DocFolder.org_id == ctx.org_id,
                                                                DocFolder.parent_folder_id == parent_id)))).scalars()  # fmt: skip
        return await folder_outs(db, [f for f in rows if access.visible(f.id)])
    if access.scoped:
        rows = (await db.execute(_order(select(DocFolder).where(DocFolder.org_id == ctx.org_id)))).scalars()
        return await folder_outs(db, [f for f in rows if access.is_scope_root(f.id)])
    rows = (await db.execute(_order(select(DocFolder).where(DocFolder.org_id == ctx.org_id,
                                                            DocFolder.parent_folder_id.is_(None))))).scalars()  # fmt: skip
    return await folder_outs(db, [f for f in rows if access.visible(f.id)])


async def get_folder_out(db: AsyncSession, ctx: TenantContext, folder_id: uuid.UUID) -> FolderOut:
    return (await folder_outs(db, [await assert_folder(db, ctx, folder_id)]))[0]


async def get_path(db: AsyncSession, ctx: TenantContext, folder_id: uuid.UUID) -> list[FolderOut]:
    await assert_folder(db, ctx, folder_id)
    access = await folder_access(db, ctx)
    return await folder_outs(db, [f for f in await folder_path(db, ctx, folder_id) if access.visible(f.id)])


async def _name_taken(db: AsyncSession, ctx: TenantContext, parent_id: uuid.UUID | None, name: str,
                      exclude: uuid.UUID | None = None) -> bool:  # fmt: skip
    cond = DocFolder.parent_folder_id.is_(None) if parent_id is None else DocFolder.parent_folder_id == parent_id
    stmt = select(DocFolder.id).where(DocFolder.org_id == ctx.org_id, cond, func.lower(DocFolder.name) == name.lower())
    if exclude:
        stmt = stmt.where(DocFolder.id != exclude)
    return (await db.execute(stmt.limit(1))).first() is not None


def _clean(name: str | None) -> str:
    clean = validate_folder_name(name)
    if clean is None:
        raise ValidationFailedError("Folder names must be 1-200 characters without slashes")
    return clean


async def create_folder(db: AsyncSession, ctx: TenantContext, body: FolderIn) -> FolderOut:
    parent = await assert_folder(db, ctx, body.parent_folder_id, CAPTURE, "WRITE")
    name = _clean(body.name)
    if await _name_taken(db, ctx, parent.id, name):
        raise AlreadyExistsError("A folder with this name already exists here")
    f = DocFolder(org_id=ctx.org_id, parent_folder_id=parent.id, name=name, system_kind="CUSTOM",
                  fy_label=parent.fy_label, month_date=parent.month_date, is_system_locked=False, created_at=now())  # fmt: skip
    db.add(f)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "CREATE", "doc_folder", f.id, after=f.to_dict())
    return (await folder_outs(db, [f]))[0]


async def update_folder(db: AsyncSession, ctx: TenantContext, folder_id: uuid.UUID, body: FolderUpdateIn) -> FolderOut:
    f = await assert_folder(db, ctx, folder_id, CAPTURE, "WRITE")
    if f.is_system_locked:
        raise FolderLockedError()
    before = f.to_dict()
    new_parent = f.parent_folder_id
    if body.parent_folder_id is not None and body.parent_folder_id != f.parent_folder_id:
        target = await assert_folder(db, ctx, body.parent_folder_id, CAPTURE, "WRITE")
        if would_create_cycle(f.id, target.id, walker(await parent_map(db, ctx))):
            raise ConflictError("A folder cannot be moved inside itself")
        new_parent = target.id
        f.fy_label, f.month_date = target.fy_label, target.month_date
    name = _clean(body.name) if body.name is not None else f.name
    if await _name_taken(db, ctx, new_parent, name, exclude=f.id):
        raise AlreadyExistsError("A folder with this name already exists here")
    f.name, f.parent_folder_id = name, new_parent
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "UPDATE", "doc_folder", f.id, before=before, after=f.to_dict(),
                      changed_only=True)  # fmt: skip
    return (await folder_outs(db, [f]))[0]


async def delete_folder(db: AsyncSession, ctx: TenantContext, folder_id: uuid.UUID) -> None:
    f = await assert_folder(db, ctx, folder_id, "documents.explorer", "FULL")
    if f.is_system_locked:
        raise FolderLockedError()
    has_child = (await db.execute(select(DocFolder.id).where(DocFolder.parent_folder_id == f.id).limit(1))).first()
    has_doc = (await db.execute(select(Document.id).where(Document.folder_id == f.id).limit(1))).first()
    if has_child or has_doc:
        raise FolderNotEmptyError()
    before = f.to_dict()
    await db.delete(f)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "DELETE", "doc_folder", folder_id, before=before)


async def ensure_month(db: AsyncSession, ctx: TenantContext, body: EnsureMonthIn) -> list[FolderOut]:
    mf = await ensure_month_folders(db, ctx, body.month)
    month = await get_folder(db, ctx, mf.month_folder_id)
    children = list((await db.execute(select(DocFolder).where(DocFolder.parent_folder_id == month.id)
                                      .order_by(DocFolder.name))).scalars())  # fmt: skip
    if mf.created:
        await write_audit(db, ctx, "DOCUMENTS", "CREATE", "doc_folder", month.id,
                          after={"month": body.month, "folders_created": mf.created})  # fmt: skip
    return await folder_outs(db, [month, *children])
