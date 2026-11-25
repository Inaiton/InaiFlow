"""Global config CRUD with effective-dated versions + push of templates to existing orgs."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import AdminPrincipal, TenantContext
from app.core.db import get_sessionmaker, set_tenant_scope
from app.core.errors import AlreadyExistsError, DomainError, InvalidStateError, NotFoundError, ValidationFailedError
from app.modules.superadmin import repository as repo
from app.modules.superadmin.audit import audit
from app.modules.superadmin.config_schemas import PUSHABLE, validate_payload
from app.modules.superadmin.schemas import (
    ConfigIn,
    ConfigOut,
    ConfigPushIn,
    ConfigPushOut,
    ConfigUpdateIn,
    ConfigVersionOut,
)

log = logging.getLogger("inaiflow.superadmin")

PushFn = Callable[[AsyncSession, TenantContext, str, dict[str, Any]], Awaitable[bool]]


def _out(r: Any) -> ConfigOut:
    m = r._mapping
    return ConfigOut(**{k: m[k] for k in ConfigOut.model_fields})


async def list_configs(db: AsyncSession, category: str | None) -> list[ConfigOut]:
    return [_out(r) for r in await repo.list_configs(db, category)]


async def get_config(db: AsyncSession, config_id: uuid.UUID) -> ConfigOut:
    r = await repo.get_config_row(db, config_id)
    if r is None:
        raise NotFoundError("Configuration not found")
    return _out(r)


async def create_config(db: AsyncSession, admin: AdminPrincipal, body: ConfigIn) -> ConfigOut:
    validate_payload(body.config_category, body.config_key, body.payload)
    if await repo.config_exists(db, body.config_category, body.config_key):
        raise AlreadyExistsError("A configuration with this category and key already exists")
    cid = await repo.insert_config(db, category=body.config_category, key=body.config_key, name=body.display_name,
                                   payload=body.payload, admin_id=admin.admin_id)  # fmt: skip
    await repo.insert_config_version(db, config_id=cid, version=1, payload=body.payload,
                                     effective_from=body.effective_from, reason=body.reason, admin_id=admin.admin_id)  # fmt: skip
    await audit(db, admin, "CONFIG_CREATE", "PLATFORM_CONFIG", cid,
                after={"category": body.config_category, "key": body.config_key, "version": 1,
                       "effective_from": body.effective_from, "payload": body.payload}, reason=body.reason)  # fmt: skip
    return await get_config(db, cid)


async def update_config(
    db: AsyncSession, admin: AdminPrincipal, config_id: uuid.UUID, body: ConfigUpdateIn
) -> ConfigOut:
    cur = await repo.lock_config(db, config_id)
    if cur is None:
        raise NotFoundError("Configuration not found")
    validate_payload(cur.config_category, cur.config_key, body.payload)
    version = cur.version + 1
    name = body.display_name or cur.display_name
    active = cur.is_active if body.is_active is None else body.is_active
    await repo.update_config(db, config_id, name=name, payload=body.payload, version=version, is_active=active,
                             admin_id=admin.admin_id)  # fmt: skip
    await repo.insert_config_version(db, config_id=config_id, version=version, payload=body.payload,
                                     effective_from=body.effective_from, reason=body.reason, admin_id=admin.admin_id)  # fmt: skip
    await audit(db, admin, "CONFIG_UPDATE", "PLATFORM_CONFIG", config_id,
                before={"version": cur.version, "display_name": cur.display_name, "is_active": cur.is_active,
                        "payload": cur.payload},
                after={"version": version, "display_name": name, "is_active": active,
                       "effective_from": body.effective_from, "payload": body.payload}, reason=body.reason)  # fmt: skip
    return await get_config(db, config_id)


async def history(db: AsyncSession, config_id: uuid.UUID) -> list[ConfigVersionOut]:
    if await repo.get_config_row(db, config_id) is None:
        raise NotFoundError("Configuration not found")
    return [ConfigVersionOut(**dict(r._mapping)) for r in await repo.config_versions(db, config_id)]


def _push_fn(category: str, key: str) -> PushFn | None:
    """Owning-module interface function that applies one template to one org, if that module exposes it.

    Requested (docs/plan/requests): operations ``install_platform_workflow_template``, documents
    ``upsert_platform_doc_template`` / ``apply_monthly_folder_rule``, rbac ``apply_system_role_permissions``.
    """
    from app.modules.documents import interface as documents
    from app.modules.operations import interface as operations
    from app.modules.rbac import interface as rbac

    if category == "ISO_WORKFLOW_TEMPLATES":
        return getattr(operations, "install_platform_workflow_template", None)
    if category == "DOC_REPORT_TEMPLATES":
        return getattr(documents, "upsert_platform_doc_template", None)
    if category == "FOLDER_TEMPLATES" and key == "MONTHLY":
        fn = getattr(documents, "apply_monthly_folder_rule", None)
        return (lambda db, ctx, _k, payload: fn(db, ctx, payload)) if fn else None
    if category == "DEFAULT_ROLES":
        fn = getattr(rbac, "apply_system_role_permissions", None)
        return (lambda db, ctx, k, payload: fn(db, ctx.org_id, k, payload["permissions"])) if fn else None
    return None


async def push(db: AsyncSession, admin: AdminPrincipal, config_id: uuid.UUID, body: ConfigPushIn) -> ConfigPushOut:
    cfg = await repo.get_config_row(db, config_id)
    if cfg is None:
        raise NotFoundError("Configuration not found")
    if cfg.config_category not in PUSHABLE:
        raise InvalidStateError(f"{cfg.config_category} applies platform-wide and cannot be pushed to organizations")
    if not cfg.is_active:
        raise InvalidStateError("Inactive configurations cannot be pushed")
    if not body.all_orgs and not body.org_ids:
        raise ValidationFailedError("Choose organizations (org_ids) or all_orgs")
    org_ids = await repo.org_ids_for_push(db, None if body.all_orgs else body.org_ids)
    requested = None if body.all_orgs else len(set(body.org_ids or []))
    fn = _push_fn(cfg.config_category, cfg.config_key)
    updated = skipped = 0
    for org_id in org_ids:
        if fn is None:
            skipped += 1
            continue
        try:  # one tenant transaction per org (RLS role), like the daily cron
            async with get_sessionmaker()() as s, s.begin():
                await set_tenant_scope(s, org_id, None)
                ok = await fn(s, TenantContext.system(org_id), cfg.config_key, dict(cfg.payload))
        except DomainError:
            log.exception("config push failed for org %s", org_id)
            ok = False
        updated, skipped = (updated + 1, skipped) if ok else (updated, skipped + 1)
    if requested is not None:
        skipped += max(0, requested - len(org_ids))  # unknown / archived orgs
    await audit(db, admin, "CONFIG_PUSH", "PLATFORM_CONFIG", config_id,
                after={"category": cfg.config_category, "key": cfg.config_key, "version": cfg.version,
                       "all_orgs": bool(body.all_orgs), "org_ids": body.org_ids, "orgs_updated": updated,
                       "orgs_skipped": skipped, "supported": fn is not None}, reason=body.reason)  # fmt: skip
    return ConfigPushOut(orgs_updated=updated, orgs_skipped=skipped)
