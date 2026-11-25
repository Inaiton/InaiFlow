"""FastAPI dependencies: DB sessions, principals, the tenant pipeline (plan §3.4), ACL helpers.

Guards carry metadata read by ``tests/test_contract.py``:
``__inaiflow_auth__`` in {"org", "user", "admin", "cron"}, ``__inaiflow_permission__`` ("key:LEVEL" | None),
``__inaiflow_admin_roles__`` (list). Routes without a guard are public.

Usage in a tenant router::

    @router.get("/organization/members", response_model=list[MemberOut])
    async def list_members(ctx: Annotated[TenantContext, Depends(require("organization.members", "READ"))],
                           db: TenantDB) -> list[MemberOut]:
        return await service.list_members(db, ctx)
"""

from __future__ import annotations

import ipaddress
import uuid
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import ColumnElement, false, not_, text, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.context import AdminPrincipal, Impersonation, Principal, TenantContext
from app.core.db import get_sessionmaker, independent_session, set_tenant_scope
from app.core.errors import (
    AccountSuspendedError,
    ForbiddenError,
    IpNotAllowedError,
    MembershipExpiredError,
    MfaRequiredError,
    NotFoundError,
    OrgSuspendedError,
    PermissionDeniedError,
    UnauthenticatedError,
    ValidationFailedError,
)
from app.core.permissions import (
    LEVELS,
    RESOURCE_TYPES,
    at_least,
    effective_permissions,
    impersonation_permissions,
    is_valid_key,
    resolve_resource_level,
)
from app.core.security import decode_access_token, decode_admin_access_token

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
ORG_HEADER = "X-Organization-ID"


# ---------------------------------------------------------------- request helpers
def client_ip(request: Request) -> str | None:
    settings = get_settings()
    if settings.VERCEL and (value := request.headers.get("x-vercel-forwarded-for")):
        return value.split(",")[0].strip()  # set by Vercel's edge, client cannot forge it
    if settings.TRUST_PROXY_HEADERS and (value := request.headers.get("x-forwarded-for")):
        # shortcut: assumes exactly one trusted proxy hop (right-most entry); add a hop count if you chain proxies
        return value.split(",")[-1].strip()
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:500] if ua else None


def bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- sessions
async def get_db() -> AsyncIterator[AsyncSession]:
    """Platform/identity session (connection user, no RLS role). One transaction, committed when the
    endpoint returns (``scope="function"`` -> before the response is sent), rolled back on error."""
    async with get_sessionmaker()() as session, session.begin():
        yield session


DB = Annotated[AsyncSession, Depends(get_db, scope="function")]


# ---------------------------------------------------------------- principals
async def get_principal(request: Request, db: DB) -> Principal:
    token = bearer_token(request)
    if not token:
        raise UnauthenticatedError()
    claims = decode_access_token(token)
    ip, ua = client_ip(request), user_agent(request)
    if claims.imp:
        imp = await _load_impersonation(db, claims.imp, claims.sid)
        return Principal(claims.sub, claims.sid, "", True, ip, ua, imp)
    row = (
        await db.execute(
            text(
                "SELECT u.is_suspended, u.email FROM user_sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.family_id = :sid AND s.user_id = :uid AND s.revoked_at IS NULL "
                "AND s.expires_at > now() LIMIT 1"
            ),
            {"sid": claims.sid, "uid": claims.sub},
        )
    ).first()
    if row is None:
        raise UnauthenticatedError("Your session has ended, please sign in again")
    if row.is_suspended:
        raise AccountSuspendedError()
    return Principal(claims.sub, claims.sid, row.email, claims.mfa, ip, ua, None)


async def _load_impersonation(db: AsyncSession, imp: dict[str, Any], sid: uuid.UUID) -> Impersonation:
    try:
        session_id = uuid.UUID(str(imp["session_id"]))
        admin_id = uuid.UUID(str(imp["admin_id"]))
        org_id = uuid.UUID(str(imp["org_id"]))
    except (KeyError, ValueError) as exc:
        raise UnauthenticatedError("Invalid token") from exc
    if session_id != sid:
        raise UnauthenticatedError("Invalid token")
    row = (
        await db.execute(
            text(
                "SELECT s.mode, s.expires_at, a.full_name FROM platform_impersonation_sessions s "
                "JOIN platform_admins a ON a.id = s.admin_id WHERE s.id = :sid AND s.admin_id = :aid "
                "AND s.org_id = :org AND s.ended_at IS NULL AND s.expires_at > now() AND a.is_active"
            ),
            {"sid": session_id, "aid": admin_id, "org": org_id},
        )
    ).first()
    if row is None:
        raise UnauthenticatedError("The impersonation session has ended")
    return Impersonation(session_id, admin_id, row.full_name, org_id, row.mode, row.expires_at)


def require_user() -> Callable[..., Any]:
    """Authenticated user, personal routes (no org header). Impersonation tokens are refused."""

    async def dep(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if principal.impersonation is not None:
            raise ForbiddenError("Impersonation sessions cannot access personal routes")
        return principal

    dep.__inaiflow_auth__ = "user"  # type: ignore[attr-defined]
    return dep


current_user = require_user()
CurrentUser = Annotated[Principal, Depends(current_user)]


# ---------------------------------------------------------------- tenant pipeline
def _org_header(request: Request) -> uuid.UUID:
    raw = request.headers.get(ORG_HEADER)
    if not raw:
        raise ValidationFailedError(f"{ORG_HEADER} header is required")
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ValidationFailedError(f"{ORG_HEADER} must be a UUID") from exc


async def get_tenant_context(
    request: Request, principal: Annotated[Principal, Depends(get_principal)], db: DB
) -> TenantContext:
    """Steps 1-3 of plan §3.4 (JWT+session, membership/expiry/org status, 2FA policy). Cached per request."""
    org_id = _org_header(request)
    if principal.impersonation is not None:
        return await _impersonation_context(request, db, principal, org_id)
    row = (
        await db.execute(
            text(
                "SELECT m.id AS membership_id, m.status, m.access_expires_at, r.id AS role_id, r.role_code, "
                "r.role_name, r.is_external_collaborator, r.permissions, o.org_status, o.owner_user_id, "
                "o.security_settings FROM org_memberships m JOIN org_roles r ON r.id = m.role_id "
                "JOIN organizations o ON o.id = m.org_id WHERE m.org_id = :org AND m.user_id = :uid"
            ),
            {"org": org_id, "uid": principal.user_id},
        )
    ).first()
    if row is None or row.status == "REVOKED":
        raise ForbiddenError("You are not a member of this organization")
    if row.status == "SUSPENDED":
        raise ForbiddenError("Your membership in this organization is suspended")
    if row.status == "EXPIRED" or (row.access_expires_at is not None and row.access_expires_at <= _utcnow()):
        raise MembershipExpiredError()
    if row.org_status in ("SUSPENDED", "ARCHIVED"):
        raise OrgSuspendedError()
    security = row.security_settings or {}
    is_external = bool(row.is_external_collaborator)
    needs_mfa = bool(security.get("enforce_2fa_all")) or (
        is_external and bool(security.get("enforce_2fa_external", True))
    )
    if needs_mfa and not principal.mfa:
        raise MfaRequiredError("This organization requires two-factor authentication")
    is_owner = row.owner_user_id == principal.user_id or row.role_code == "ORG_OWNER"
    return TenantContext(
        org_id=org_id,
        user_id=principal.user_id,
        membership_id=row.membership_id,
        role_code=row.role_code,
        role_id=row.role_id,
        is_external=is_external,
        is_owner=is_owner,
        permissions=effective_permissions(row.permissions, is_owner=is_owner),
        mfa=principal.mfa,
        ip=principal.ip,
        user_agent=principal.user_agent,
        actor_type="USER",
        actor_id=principal.user_id,
        role_name=row.role_name,
    )


async def _impersonation_context(
    request: Request, db: AsyncSession, principal: Principal, org_id: uuid.UUID
) -> TenantContext:
    imp = principal.impersonation
    if imp is None:
        raise NotFoundError()
    if imp.org_id != org_id:
        raise ForbiddenError("The impersonation session is for another organization")
    owner_id = (await db.execute(text("SELECT owner_user_id FROM organizations WHERE id = :o"), {"o": org_id})).scalar()
    if owner_id is None:
        raise NotFoundError()
    mutating = request.method not in SAFE_METHODS
    if mutating and imp.mode != "FULL_SUPPORT":
        raise ForbiddenError("Read-only support session: changes are not allowed")
    if mutating:
        await _audit_impersonated_request(request, imp, principal.ip)
    return TenantContext(
        org_id=org_id,
        user_id=owner_id,
        membership_id=None,
        role_code="SUPPORT_IMPERSONATION",
        role_id=None,
        is_external=False,
        is_owner=False,
        permissions=impersonation_permissions(imp.mode),
        mfa=True,
        impersonation=imp,
        ip=principal.ip,
        user_agent=principal.user_agent,
        actor_type="PLATFORM_ADMIN",
        actor_id=imp.admin_id,
        role_name="Support (impersonation)",
    )


async def _audit_impersonated_request(request: Request, imp: Impersonation, ip: str | None) -> None:
    import json

    async with independent_session() as s:
        await s.execute(
            text(
                "INSERT INTO platform_audit_logs (superadmin_id, action, target_type, target_id, after_state, "
                "ip_address) VALUES (:aid, 'IMPERSONATED_REQUEST', 'ORGANIZATION', :org, CAST(:after AS jsonb), "
                "CAST(:ip AS inet))"
            ),
            {
                "aid": imp.admin_id,
                "org": imp.org_id,
                "after": json.dumps(
                    {"method": request.method, "path": request.url.path, "session_id": str(imp.session_id)}
                ),
                "ip": _valid_ip(ip),
            },
        )


def _valid_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


TenantBase = Annotated[TenantContext, Depends(get_tenant_context)]


def require(permission_key: str | None, level: str = "READ", *, acl_resource: str | None = None) -> Callable[..., Any]:
    """Tenant guard. ``permission_key=None`` = any active member ("org member" in the contract).

    ``acl_resource`` (STOCK_ITEM | PERIOD_RUN | DOC_FOLDER | GODOWN): also admit callers whose module level is
    too low but who hold a resource ACL grant >= ``level`` on at least one resource of that type (the
    service must then filter with ``acl_list_filter``/``assert_resource_access``).
    """
    if permission_key is not None and not is_valid_key(permission_key):
        raise ValueError(f"unknown permission key {permission_key!r}")
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    if acl_resource is not None and acl_resource not in RESOURCE_TYPES:
        raise ValueError(f"unknown resource type {acl_resource!r}")

    async def dep(ctx: TenantBase, db: DB) -> TenantContext:
        if permission_key is None or ctx.has(permission_key, level):
            return ctx
        if acl_resource and ctx.user_id and await _has_any_grant(db, ctx, acl_resource, level):
            return ctx
        raise PermissionDeniedError(details={"permission": permission_key, "required": level})

    dep.__inaiflow_auth__ = "org"  # type: ignore[attr-defined]
    dep.__inaiflow_permission__ = f"{permission_key}:{level}" if permission_key else None  # type: ignore[attr-defined]
    return dep


async def _has_any_grant(db: AsyncSession, ctx: TenantContext, resource_type: str, level: str) -> bool:
    wanted = [lvl for lvl in LEVELS if at_least(lvl, level)]
    found = (
        await db.execute(
            text(
                "SELECT 1 FROM resource_acl WHERE org_id = :org AND resource_type = :rt "
                "AND access_level = ANY(:levels) AND ((subject_type = 'USER' AND subject_id = :uid) "
                "OR (subject_type = 'ROLE' AND subject_id = :rid)) LIMIT 1"
            ),
            {"org": ctx.org_id, "rt": resource_type, "levels": wanted, "uid": ctx.user_id, "rid": ctx.role_id},
        )
    ).first()
    return found is not None


async def get_tenant_db(ctx: TenantBase) -> AsyncIterator[AsyncSession]:
    """RLS-scoped session: ONE transaction with ``SET LOCAL ROLE inaiflow_app`` + org/user GUCs.

    Commits right after the endpoint function returns and *before* the response is sent (declared with
    ``scope="function"``), so commit-time failures (deferred triggers, constraint violations) become error
    responses instead of a 2xx with lost data.
    """
    async with get_sessionmaker()() as session, session.begin():
        await set_tenant_scope(session, ctx.org_id, ctx.user_id)
        yield session


TenantDB = Annotated[AsyncSession, Depends(get_tenant_db, scope="function")]


# ---------------------------------------------------------------- resource ACL
async def acl_overrides(
    ctx: TenantContext, db: AsyncSession, resource_type: str, resource_ids: Iterable[uuid.UUID] | None = None
) -> dict[uuid.UUID, str]:
    """Effective override per resource for the caller: USER row beats ROLE row."""
    if ctx.user_id is None or ctx.role_id is None:
        return {}
    sql = (
        "SELECT resource_id, subject_type, access_level FROM resource_acl WHERE org_id = :org "
        "AND resource_type = :rt AND ((subject_type = 'USER' AND subject_id = :uid) "
        "OR (subject_type = 'ROLE' AND subject_id = :rid))"
    )
    params: dict[str, Any] = {"org": ctx.org_id, "rt": resource_type, "uid": ctx.user_id, "rid": ctx.role_id}
    if resource_ids is not None:
        ids = list(resource_ids)
        if not ids:
            return {}
        sql += " AND resource_id = ANY(:ids)"
        params["ids"] = ids
    user_rows: dict[uuid.UUID, str] = {}
    role_rows: dict[uuid.UUID, str] = {}
    for rid, subject_type, lvl in (await db.execute(text(sql), params)).all():
        (user_rows if subject_type == "USER" else role_rows)[rid] = lvl
    return {**role_rows, **user_rows}


async def resource_level(
    ctx: TenantContext, db: AsyncSession, resource_type: str, resource_id: uuid.UUID, module_key: str
) -> str:
    if ctx.is_owner:
        return "FULL"
    overrides = await acl_overrides(ctx, db, resource_type, [resource_id])
    user_or_role = overrides.get(resource_id)
    return resolve_resource_level(ctx.level(module_key), user_override=user_or_role, role_override=None, is_owner=False)


async def assert_resource_access(
    ctx: TenantContext,
    db: AsyncSession,
    resource_type: str,
    resource_id: uuid.UUID,
    module_key: str,
    level: str = "READ",
) -> str:
    """Raise NOT_FOUND when the effective level is NONE (never leak existence), PERMISSION_DENIED when lower
    than ``level``. Returns the effective level."""
    eff = await resource_level(ctx, db, resource_type, resource_id, module_key)
    if eff == "NONE":
        raise NotFoundError()
    if not at_least(eff, level):
        raise PermissionDeniedError(details={"permission": module_key, "required": level, "resource": resource_type})
    return eff


async def filter_accessible(
    ctx: TenantContext,
    db: AsyncSession,
    resource_type: str,
    resource_ids: Iterable[uuid.UUID],
    module_key: str,
    level: str = "READ",
) -> list[uuid.UUID]:
    ids = list(resource_ids)
    if ctx.is_owner:
        return ids
    overrides = await acl_overrides(ctx, db, resource_type, ids)
    module_level = ctx.level(module_key)
    return [i for i in ids if at_least(overrides.get(i, module_level), level)]


@dataclass(frozen=True, slots=True)
class AclFilter:
    """SQL-side list filtering: ``stmt.where(f.clause(Model.id))``."""

    module_level: str
    allowed: frozenset[uuid.UUID]  # overrides >= level
    denied: frozenset[uuid.UUID]  # overrides < level
    level: str = "READ"

    def clause(self, id_column: Any) -> ColumnElement[bool]:
        if at_least(self.module_level, self.level):
            return not_(id_column.in_(self.denied)) if self.denied else true()
        return id_column.in_(self.allowed) if self.allowed else false()

    def visible(self, resource_id: uuid.UUID) -> bool:
        if resource_id in self.denied:
            return False
        return resource_id in self.allowed or at_least(self.module_level, self.level)


async def acl_list_filter(
    ctx: TenantContext, db: AsyncSession, resource_type: str, module_key: str, level: str = "READ"
) -> AclFilter:
    if ctx.is_owner:
        return AclFilter("FULL", frozenset(), frozenset(), level)
    overrides = await acl_overrides(ctx, db, resource_type)
    allowed = frozenset(k for k, v in overrides.items() if at_least(v, level))
    denied = frozenset(k for k, v in overrides.items() if not at_least(v, level))
    return AclFilter(ctx.level(module_key), allowed, denied, level)


# ---------------------------------------------------------------- admin & cron
def _ip_allowed(ip: str | None, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for cidr in allowlist:
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def check_admin_ip(request: Request) -> str | None:
    """Raise IP_NOT_ALLOWED unless the caller matches ADMIN_IP_ALLOWLIST (use on public admin auth routes)."""
    ip = client_ip(request)
    if not _ip_allowed(ip, get_settings().admin_ip_allowlist):
        raise IpNotAllowedError()
    return ip


async def get_admin_principal(request: Request, db: DB) -> AdminPrincipal:
    ip = check_admin_ip(request)
    token = bearer_token(request)
    if not token:
        raise UnauthenticatedError()
    claims = decode_admin_access_token(token)
    try:
        admin_id, sid = uuid.UUID(claims["sub"]), uuid.UUID(claims["sid"])
    except (KeyError, ValueError) as exc:
        raise UnauthenticatedError("Invalid token") from exc
    row = (
        await db.execute(
            text(
                "SELECT a.email, a.role, a.is_active FROM admin_sessions s JOIN platform_admins a "
                "ON a.id = s.admin_id WHERE s.family_id = :sid AND s.admin_id = :aid AND s.revoked_at IS NULL "
                "AND s.expires_at > now() LIMIT 1"
            ),
            {"sid": sid, "aid": admin_id},
        )
    ).first()
    if row is None or not row.is_active:
        raise UnauthenticatedError("Your admin session has ended")
    return AdminPrincipal(admin_id, sid, row.email, row.role, ip, user_agent(request))


def require_admin(*roles: str) -> Callable[..., Any]:
    """Platform admin guard. ``require_admin()`` / ``require_admin("ANY")`` = any admin role."""
    allowed = [r for r in roles if r != "ANY"]

    async def dep(admin: Annotated[AdminPrincipal, Depends(get_admin_principal)]) -> AdminPrincipal:
        if allowed and admin.role not in allowed and admin.role != "SUPERADMIN":
            raise ForbiddenError("Your admin role does not allow this action")
        return admin

    dep.__inaiflow_auth__ = "admin"  # type: ignore[attr-defined]
    dep.__inaiflow_admin_roles__ = allowed or ["ANY"]  # type: ignore[attr-defined]
    return dep


def require_cron() -> Callable[..., Any]:
    async def dep(request: Request) -> None:
        from app.core.security import constant_time_equals

        token = bearer_token(request)
        if not token or not constant_time_equals(token, get_settings().CRON_SECRET):
            raise UnauthenticatedError()

    dep.__inaiflow_auth__ = "cron"  # type: ignore[attr-defined]
    return dep


def guard_of(dependency: Any) -> tuple[str, str | None, list[str] | None] | None:
    """(auth, permission, admin_roles) for a guard callable, else None (used by the contract test)."""
    auth = getattr(dependency, "__inaiflow_auth__", None)
    if auth is None:
        return None
    return (
        auth,
        getattr(dependency, "__inaiflow_permission__", None),
        getattr(dependency, "__inaiflow_admin_roles__", None),
    )


__all__ = [
    "DB",
    "AclFilter",
    "CurrentUser",
    "TenantBase",
    "TenantDB",
    "acl_list_filter",
    "acl_overrides",
    "assert_resource_access",
    "check_admin_ip",
    "client_ip",
    "current_user",
    "filter_accessible",
    "get_db",
    "get_principal",
    "get_tenant_context",
    "get_tenant_db",
    "guard_of",
    "require",
    "require_admin",
    "require_cron",
    "require_user",
    "resource_level",
    "user_agent",
]
