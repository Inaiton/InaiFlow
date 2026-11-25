"""Low-level documents helpers shared by services and ``interface.py``: folder loading, DOC_FOLDER ACL
(inherited down the tree), path building, run folders and generated files."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage import build_org_key, get_storage
from app.core.context import TenantContext
from app.core.deps import acl_overrides
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.permissions import at_least
from app.modules.documents.models import DocFolder, Document
from app.modules.documents.seeding import ensure_month_folders

EXPLORER = "documents.explorer"


def now() -> datetime:
    return datetime.now(UTC)


async def get_folder(db: AsyncSession, ctx: TenantContext, folder_id: uuid.UUID) -> DocFolder:
    f = await db.get(DocFolder, folder_id)
    if f is None or f.org_id != ctx.org_id:
        raise NotFoundError("Folder not found")
    return f


async def get_doc(db: AsyncSession, ctx: TenantContext, doc_id: uuid.UUID) -> Document:
    d = await db.get(Document, doc_id)
    if d is None or d.org_id != ctx.org_id:
        raise NotFoundError("Document not found")
    return d


async def parent_map(db: AsyncSession, ctx: TenantContext) -> dict[uuid.UUID, uuid.UUID | None]:
    rows = await db.execute(select(DocFolder.id, DocFolder.parent_folder_id).where(DocFolder.org_id == ctx.org_id))
    return dict(rows.all())


class FolderAccess:
    """Effective level per folder: nearest ancestor ACL override (USER beats ROLE) else the module level.
    External collaborators holding DOC_FOLDER grants are scoped: folders outside granted subtrees = NONE."""

    def __init__(self, ctx: TenantContext, overrides: dict[uuid.UUID, str],
                 parents: dict[uuid.UUID, uuid.UUID | None]) -> None:  # fmt: skip
        self.ctx, self.overrides, self.parents = ctx, overrides, parents
        self.scoped = ctx.is_external and not ctx.is_owner and any(at_least(v, "READ") for v in overrides.values())

    def level(self, folder_id: uuid.UUID, key: str = EXPLORER) -> str:
        if self.ctx.is_owner:
            return "FULL"
        cur: uuid.UUID | None = folder_id
        hops = 0
        while cur is not None and hops < 1000:
            if cur in self.overrides:
                return self.overrides[cur]
            cur, hops = self.parents.get(cur), hops + 1
        return "NONE" if self.scoped else self.ctx.level(key)

    def visible(self, folder_id: uuid.UUID) -> bool:
        return at_least(self.level(folder_id), "READ")

    def is_scope_root(self, folder_id: uuid.UUID) -> bool:
        """A visible folder whose parent is not visible (shown at the top level for scoped users)."""
        parent = self.parents.get(folder_id)
        return self.visible(folder_id) and (parent is None or not self.visible(parent))


async def folder_access(db: AsyncSession, ctx: TenantContext) -> FolderAccess:
    overrides = {} if ctx.is_owner else await acl_overrides(ctx, db, "DOC_FOLDER")
    parents = await parent_map(db, ctx) if overrides else {}
    return FolderAccess(ctx, overrides, parents)


async def assert_folder(
    db: AsyncSession, ctx: TenantContext, folder_id: uuid.UUID, key: str = EXPLORER, level: str = "READ"
) -> DocFolder:
    folder = await get_folder(db, ctx, folder_id)
    access = await folder_access(db, ctx)
    if not access.visible(folder.id):
        raise NotFoundError("Folder not found")
    if not at_least(access.level(folder.id, key), level):
        raise PermissionDeniedError(details={"permission": key, "required": level, "resource": "DOC_FOLDER"})
    return folder


async def folder_path(db: AsyncSession, ctx: TenantContext, folder_id: uuid.UUID) -> list[DocFolder]:
    out: list[DocFolder] = []
    cur: uuid.UUID | None = folder_id
    while cur is not None and len(out) < 100:
        f = await db.get(DocFolder, cur)
        if f is None or f.org_id != ctx.org_id:
            break
        out.append(f)
        cur = f.parent_folder_id
    return list(reversed(out))


async def unique_child_name(db: AsyncSession, ctx: TenantContext, parent_id: uuid.UUID, name: str) -> str:
    taken = set((await db.execute(select(DocFolder.name).where(
        DocFolder.org_id == ctx.org_id, DocFolder.parent_folder_id == parent_id))).scalars())  # fmt: skip
    if name not in taken:
        return name
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"


async def create_run_folder(
    db: AsyncSession, ctx: TenantContext, *, run_id: uuid.UUID, run_title: str, month: date
) -> uuid.UUID:
    mf = await ensure_month_folders(db, ctx, month)
    existing = (await db.execute(select(DocFolder.id).where(
        DocFolder.org_id == ctx.org_id, DocFolder.linked_period_run_id == run_id))).scalar()  # fmt: skip
    if existing:
        return existing
    name = await unique_child_name(db, ctx, mf.operations_id, run_title.strip()[:200] or "Run")
    parent = await db.get(DocFolder, mf.operations_id)
    folder = DocFolder(org_id=ctx.org_id, parent_folder_id=mf.operations_id, name=name, system_kind="RUN",
                       fy_label=parent.fy_label if parent else None, month_date=parent.month_date if parent else None,
                       is_system_locked=True, linked_period_run_id=run_id, created_at=now())  # fmt: skip
    db.add(folder)
    await db.flush()
    return folder.id


async def store_generated_file(
    db: AsyncSession, ctx: TenantContext, *, folder_id: uuid.UUID, title: str, mime: str, data: bytes,
    source_type: str, file_name: str | None = None, linked_voucher_id: uuid.UUID | None = None,
    linked_period_run_id: uuid.UUID | None = None, linked_step_id: uuid.UUID | None = None,
    linked_stock_item_id: uuid.UUID | None = None,
) -> uuid.UUID:  # fmt: skip
    from app.core.audit import write_audit

    await get_folder(db, ctx, folder_id)
    preparer = ctx.user_id
    if preparer is None:
        from app.modules.organization import interface as organization

        org = await organization.get_org_brief(db, ctx.org_id)
        preparer = org.owner_user_id if org else None
    name = file_name or title
    key = build_org_key(ctx.org_id, name)
    await get_storage().put_bytes(key, data, mime)
    doc = Document(org_id=ctx.org_id, folder_id=folder_id, title=title[:255], source_type=source_type,
                   file_name=name[:255], file_mime_type=mime, file_size=len(data),
                   checksum_sha256=hashlib.sha256(data).hexdigest(), storage_key=key, upload_status="READY",
                   linked_voucher_id=linked_voucher_id, linked_period_run_id=linked_period_run_id,
                   linked_step_id=linked_step_id, linked_stock_item_id=linked_stock_item_id,
                   prepared_by=preparer, approval_status="DRAFT", revision_no=1,
                   created_at=now(), updated_at=now())  # fmt: skip
    db.add(doc)
    await db.flush()
    await write_audit(db, ctx, "DOCUMENTS", "CREATE", "document", doc.id,
                      after={"title": doc.title, "source_type": source_type, "folder_id": folder_id})  # fmt: skip
    return doc.id


def walker(parents: dict[uuid.UUID, uuid.UUID | None]) -> Callable[[uuid.UUID], uuid.UUID | None]:
    return lambda fid: parents.get(fid)
