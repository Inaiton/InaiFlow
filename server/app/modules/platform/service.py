"""Platform services: health, metadata, daily cron, dev-only local storage."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage import LocalStorage, get_storage
from app.core.config import get_settings
from app.core.context import TenantContext
from app.core.db import get_sessionmaker, set_tenant_scope
from app.core.errors import DomainError, FileTooLargeError, NotFoundError, UnauthenticatedError
from app.core.permissions import PERMISSION_CATALOG
from app.modules.documents import interface as documents
from app.modules.operations import interface as operations
from app.modules.organization import interface as organization
from app.modules.platform.interface import get_config
from app.modules.platform.schemas import CronResultOut, HealthOut, PermissionKeyOut, PermissionModuleOut, StateOut

log = logging.getLogger("inaiflow.cron")


async def health(db: AsyncSession) -> HealthOut:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001
        db_status = "error"
    return HealthOut(status="ok" if db_status == "ok" else "degraded", version=get_settings().APP_VERSION,
                     db=db_status)  # fmt: skip


async def states(db: AsyncSession) -> list[StateOut]:
    payload = await get_config(db, "INDIAN_STATES", "default")
    return [StateOut(code=s["code"], name=s["name"]) for s in payload["states"]]


def permission_keys() -> list[PermissionModuleOut]:
    return [
        PermissionModuleOut(
            module=m["module"],
            label=m["label"],
            keys=[
                PermissionKeyOut(key=f"{m['module']}.{k}", label=label, description=desc)
                for k, label, desc in m["keys"]
            ],  # fmt: skip
        )
        for m in PERMISSION_CATALOG
    ]


async def run_daily_cron(db: AsyncSession) -> CronResultOut:
    """Expire invitations/memberships, then per org (own tenant transaction): month folders + calibration."""
    today = datetime.now(UTC).date()
    invitations_expired = await organization.expire_invitations(db)
    memberships_expired = await organization.expire_memberships(db)
    await db.execute(text("DELETE FROM idempotency_keys WHERE created_at < now() - interval '24 hours'"))
    org_ids = await organization.list_active_org_ids(db)
    folders = instruments = processed = 0
    for org_id in org_ids:
        try:
            async with get_sessionmaker()() as s, s.begin():
                await set_tenant_scope(s, org_id, None)
                ctx = TenantContext.system(org_id)
                month = await documents.ensure_month_folders(s, ctx, today)
                folders += month.created
                instruments += await operations.refresh_calibration_statuses(s, ctx, today)
            processed += 1
        except DomainError:
            log.exception("cron failed for org %s", org_id)
    return CronResultOut(orgs_processed=processed, folders_created=folders, instruments_updated=instruments,
                         invitations_expired=invitations_expired, memberships_expired=memberships_expired)  # fmt: skip


def _local_storage() -> LocalStorage:
    storage = get_storage()
    if get_settings().STORAGE_PROVIDER != "local" or not isinstance(storage, LocalStorage):
        raise NotFoundError()
    return storage


async def local_put(token: str, data: bytes, content_type: str | None) -> None:
    storage = _local_storage()
    try:
        payload = storage.verify_token(token, "put")
    except DomainError as exc:
        raise UnauthenticatedError("Invalid or expired upload URL") from exc
    if len(data) > int(payload.get("max") or 0):
        raise FileTooLargeError()
    await storage.put_bytes(payload["key"], data, payload.get("ct") or content_type or "application/octet-stream")


async def local_get(token: str) -> tuple[bytes, str, str | None]:
    storage = _local_storage()
    try:
        payload = storage.verify_token(token, "get")
    except DomainError as exc:
        raise NotFoundError() from exc
    info = await storage.head(payload["key"])
    if info is None:
        raise NotFoundError()
    return await storage.get_bytes(payload["key"]), info.content_type or "application/octet-stream", payload.get("fn")
