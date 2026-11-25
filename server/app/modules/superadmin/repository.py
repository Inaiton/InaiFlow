"""Superadmin data access. Never commits.

* Own tables (ORM): platform_admins, admin_sessions, platform_audit_logs, platform_subscription_invoices,
  platform_impersonation_sessions.
* Platform control-plane tables managed by the console (plan §3.6 "superadmin: configs, plans, billing"):
  platform_global_configs / _versions and platform_subscription_plans — SQL here because their ORM models live in
  ``platform.models`` (private to that module); reads for services go through ``platform.interface``.
* **Platform reporting reads** (documented exception, decisions/S5.md): read-only cross-tenant aggregates for the
  directory/dashboard (organizations, users, memberships, vouchers, period_runs, documents). They run on the platform
  session (no RLS role) and never write. Every *mutation* of tenant data goes through the owning module's interface.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.superadmin.models import (
    AdminSession,
    PlatformAdmin,
    PlatformImpersonationSession,
    PlatformSubscriptionInvoice,
)


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def _page(db: AsyncSession, base: str, select_sql: str, order: str, params: dict[str, Any],
                limit: int, offset: int) -> tuple[list[Any], int]:  # fmt: skip
    total = (await db.execute(text(f"SELECT count(*) {base}"), params)).scalar_one()  # noqa: S608 - fixed fragments
    rows = (
        await db.execute(
            text(f"{select_sql} {base} ORDER BY {order} LIMIT :_l OFFSET :_o"),  # noqa: S608
            {**params, "_l": limit, "_o": offset},
        )  # fmt: skip
    ).all()
    return list(rows), int(total)


# ================================================================= admins & sessions
async def admin_by_email(db: AsyncSession, email: str) -> PlatformAdmin | None:
    return (await db.execute(select(PlatformAdmin).where(PlatformAdmin.email == email))).scalar_one_or_none()


async def admin_by_id(db: AsyncSession, admin_id: uuid.UUID, *, lock: bool = False) -> PlatformAdmin | None:
    stmt = select(PlatformAdmin).where(PlatformAdmin.id == admin_id)
    if lock:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_admins(db: AsyncSession) -> list[PlatformAdmin]:
    return list((await db.execute(select(PlatformAdmin).order_by(PlatformAdmin.created_at))).scalars())


async def count_active_superadmins(db: AsyncSession) -> int:
    stmt = select(func.count()).where(PlatformAdmin.role == "SUPERADMIN", PlatformAdmin.is_active)
    return int((await db.execute(stmt)).scalar_one())


async def lock_admins(db: AsyncSession) -> None:
    """Serialize role/activation changes (last-SUPERADMIN rule)."""
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('inaiflow.platform_admins'))"))


async def add(db: AsyncSession, obj: object) -> None:
    db.add(obj)
    await db.flush()


async def session_by_hash(db: AsyncSession, token_hash: str) -> AdminSession | None:
    return (await db.execute(select(AdminSession).where(AdminSession.token_hash == token_hash))).scalar_one_or_none()


async def claim_rotation(db: AsyncSession, session_id: uuid.UUID) -> bool:
    res = await db.execute(
        update(AdminSession)
        .where(AdminSession.id == session_id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=func.now(), revoke_reason="ROTATED", last_used_at=func.now())
        .returning(AdminSession.id)
    )
    return res.first() is not None


async def set_replaced_by(db: AsyncSession, session_id: uuid.UUID, new_id: uuid.UUID) -> None:
    await db.execute(update(AdminSession).where(AdminSession.id == session_id).values(replaced_by_id=new_id))


async def revoke_family(db: AsyncSession, family_id: uuid.UUID, reason: str) -> None:
    await db.execute(
        update(AdminSession)
        .where(AdminSession.family_id == family_id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=func.now(), revoke_reason=reason)
    )


async def revoke_admin_sessions(db: AsyncSession, admin_id: uuid.UUID, reason: str,
                                except_family: uuid.UUID | None = None) -> None:  # fmt: skip
    stmt = update(AdminSession).where(AdminSession.admin_id == admin_id, AdminSession.revoked_at.is_(None))
    if except_family is not None:
        stmt = stmt.where(AdminSession.family_id != except_family)
    await db.execute(stmt.values(revoked_at=func.now(), revoke_reason=reason))


# ================================================================= impersonation
async def end_impersonations(db: AsyncSession, *, org_id: uuid.UUID | None = None,
                             admin_id: uuid.UUID | None = None) -> None:  # fmt: skip
    stmt = update(PlatformImpersonationSession).where(PlatformImpersonationSession.ended_at.is_(None))
    if org_id is not None:
        stmt = stmt.where(PlatformImpersonationSession.org_id == org_id)
    if admin_id is not None:
        stmt = stmt.where(PlatformImpersonationSession.admin_id == admin_id)
    await db.execute(stmt.values(ended_at=func.now()))


# ================================================================= audit
async def audit_page(db: AsyncSession, *, action: str | None, target_type: str | None, admin_id: uuid.UUID | None,
                     date_from: date | None, date_to: date | None, limit: int, offset: int) -> tuple[list[Any], int]:  # fmt: skip
    where, p = ["true"], {}
    if action:
        where.append("l.action = :action")
        p["action"] = action
    if target_type:
        where.append("l.target_type = :tt")
        p["tt"] = target_type
    if admin_id:
        where.append("l.superadmin_id = :aid")
        p["aid"] = admin_id
    if date_from:
        where.append("l.created_at >= CAST(:df AS date)")
        p["df"] = date_from
    if date_to:
        where.append("l.created_at < CAST(:dt AS date) + 1")
        p["dt"] = date_to
    base = (
        f"FROM platform_audit_logs l LEFT JOIN platform_admins a ON a.id = l.superadmin_id WHERE {' AND '.join(where)}"
    )
    sel = ("SELECT l.id, l.superadmin_id AS admin_id, a.email AS admin_email, l.action, l.target_type, l.target_id, "
           "l.before_state, l.after_state, host(l.ip_address) AS ip_address, l.created_at")  # fmt: skip
    return await _page(db, base, sel, "l.created_at DESC, l.id", p, limit, offset)


# ================================================================= configs (platform control plane)
_CONFIG_SELECT = (
    "SELECT c.id, c.config_category, c.config_key, c.display_name, c.payload, c.version, c.is_active, "
    "c.updated_at, a.full_name AS updated_by_name, "
    "(SELECT v.effective_from FROM platform_global_config_versions v WHERE v.config_id = c.id "
    " AND v.version = c.version) AS effective_from "
    "FROM platform_global_configs c LEFT JOIN platform_admins a ON a.id = c.updated_by"
)


async def list_configs(db: AsyncSession, category: str | None) -> list[Any]:
    sql, p = _CONFIG_SELECT, {}
    if category:
        sql += " WHERE c.config_category = :c"
        p["c"] = category
    return list((await db.execute(text(sql + " ORDER BY c.config_category, c.config_key"), p)).all())


async def get_config_row(db: AsyncSession, config_id: uuid.UUID) -> Any | None:
    return (await db.execute(text(_CONFIG_SELECT + " WHERE c.id = :i"), {"i": config_id})).first()


async def lock_config(db: AsyncSession, config_id: uuid.UUID) -> Any | None:
    return (
        await db.execute(text("SELECT * FROM platform_global_configs WHERE id = :i FOR UPDATE"), {"i": config_id})
    ).first()


async def config_exists(db: AsyncSession, category: str, key: str) -> bool:
    row = await db.execute(
        text("SELECT 1 FROM platform_global_configs WHERE config_category = :c AND config_key = :k"),
        {"c": category, "k": key},
    )
    return row.first() is not None


async def insert_config(
    db: AsyncSession, *, category: str, key: str, name: str, payload: dict, admin_id: uuid.UUID
) -> uuid.UUID:
    return (
        await db.execute(
            text(
                "INSERT INTO platform_global_configs (config_category, config_key, display_name, payload, version, "
                "updated_by) VALUES (:c, :k, :n, CAST(:p AS jsonb), 1, :a) RETURNING id"
            ),
            {"c": category, "k": key, "n": name, "p": json.dumps(payload), "a": admin_id},
        )  # fmt: skip
    ).scalar_one()


async def update_config(db: AsyncSession, config_id: uuid.UUID, *, name: str, payload: dict, version: int,
                        is_active: bool, admin_id: uuid.UUID) -> None:  # fmt: skip
    await db.execute(
        text("UPDATE platform_global_configs SET display_name = :n, payload = CAST(:p AS jsonb), version = :v, "
             "is_active = :act, updated_by = :a, updated_at = now() WHERE id = :i"),
        {"n": name, "p": json.dumps(payload), "v": version, "act": is_active, "a": admin_id, "i": config_id},
    )  # fmt: skip


async def insert_config_version(db: AsyncSession, *, config_id: uuid.UUID, version: int, payload: dict,
                                effective_from: date | None, reason: str, admin_id: uuid.UUID) -> None:  # fmt: skip
    await db.execute(
        text("INSERT INTO platform_global_config_versions (config_id, version, payload, effective_from, "
             "change_reason, created_by) VALUES (:i, :v, CAST(:p AS jsonb), :ef, :r, :a)"),
        {"i": config_id, "v": version, "p": json.dumps(payload), "ef": effective_from, "r": reason, "a": admin_id},
    )  # fmt: skip


async def config_versions(db: AsyncSession, config_id: uuid.UUID) -> list[Any]:
    return list(
        (
            await db.execute(
                text(
                    "SELECT v.version, v.payload, v.effective_from, v.change_reason, a.full_name AS created_by_name, "
                    "v.created_at FROM platform_global_config_versions v LEFT JOIN platform_admins a "
                    "ON a.id = v.created_by WHERE v.config_id = :i ORDER BY v.version DESC"
                ),
                {"i": config_id},
            )  # fmt: skip
        ).all()
    )


# ================================================================= plans (platform control plane)
_PLAN_SELECT = (
    "SELECT p.id, p.plan_code, p.name, p.monthly_price_inr, p.annual_price_inr, p.max_internal_seats, "
    "p.max_external_collaborators, p.max_storage_gb, p.enabled_modules, p.is_active, p.created_at, "
    "(SELECT count(*) FROM organizations o WHERE o.plan_id = p.id) AS org_count FROM platform_subscription_plans p"
)
PLAN_COLUMNS = ("name", "monthly_price_inr", "annual_price_inr", "max_internal_seats", "max_external_collaborators",
                "max_storage_gb", "enabled_modules", "is_active")  # fmt: skip


async def list_plans(db: AsyncSession) -> list[Any]:
    return list((await db.execute(text(_PLAN_SELECT + " ORDER BY p.monthly_price_inr, p.plan_code"))).all())


async def get_plan(db: AsyncSession, plan_id: uuid.UUID) -> Any | None:
    return (await db.execute(text(_PLAN_SELECT + " WHERE p.id = :i"), {"i": plan_id})).first()


async def plan_code_taken(db: AsyncSession, code: str) -> bool:
    row = await db.execute(text("SELECT 1 FROM platform_subscription_plans WHERE plan_code = :c"), {"c": code})
    return row.first() is not None


async def insert_plan(db: AsyncSession, values: dict[str, Any]) -> uuid.UUID:
    return (
        await db.execute(
            text(
                "INSERT INTO platform_subscription_plans (plan_code, name, monthly_price_inr, annual_price_inr, "
                "max_internal_seats, max_external_collaborators, max_storage_gb, enabled_modules, is_active) VALUES "
                "(:plan_code, :name, :monthly_price_inr, :annual_price_inr, :max_internal_seats, "
                ":max_external_collaborators, :max_storage_gb, CAST(:enabled_modules AS jsonb), :is_active) RETURNING id"
            ),
            {**values, "enabled_modules": json.dumps(values["enabled_modules"])},
        )  # fmt: skip
    ).scalar_one()


async def update_plan(db: AsyncSession, plan_id: uuid.UUID, values: dict[str, Any]) -> None:
    cols = [c for c in PLAN_COLUMNS if c in values]
    if not cols:
        return
    sets = ", ".join(f"{c} = CAST(:{c} AS jsonb)" if c == "enabled_modules" else f"{c} = :{c}" for c in cols)
    params = {c: json.dumps(values[c]) if c == "enabled_modules" else values[c] for c in cols}
    await db.execute(text(f"UPDATE platform_subscription_plans SET {sets} WHERE id = :_id"),  # noqa: S608
                     {**params, "_id": plan_id})  # fmt: skip


# ================================================================= invoices
async def invoice_page(db: AsyncSession, *, org_id: uuid.UUID | None, status: str | None, limit: int,
                       offset: int) -> tuple[list[Any], int]:  # fmt: skip
    where, p = ["true"], {}
    if org_id:
        where.append("i.org_id = :org")
        p["org"] = org_id
    if status:
        where.append("i.status = :st")
        p["st"] = status
    base = f"FROM platform_subscription_invoices i JOIN organizations o ON o.id = i.org_id WHERE {' AND '.join(where)}"
    sel = ("SELECT i.id, i.org_id, o.legal_name AS org_name, i.invoice_number, i.period_start, i.period_end, "
           "i.amount_inr, i.status, i.paid_at, i.created_at")  # fmt: skip
    return await _page(db, base, sel, "i.created_at DESC, i.invoice_number DESC", p, limit, offset)


async def invoice_by_id(
    db: AsyncSession, invoice_id: uuid.UUID, *, lock: bool = False
) -> PlatformSubscriptionInvoice | None:
    stmt = select(PlatformSubscriptionInvoice).where(PlatformSubscriptionInvoice.id == invoice_id)
    if lock:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def next_invoice_number(db: AsyncSession, prefix: str) -> str:
    """``INV-YYYYMM-####`` — serialized per month with an advisory lock (gap-free within a month)."""
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"inaiflow.invoice.{prefix}"})
    last = (
        await db.execute(
            text("SELECT max(invoice_number) FROM platform_subscription_invoices WHERE invoice_number LIKE :p"),
            {"p": f"{prefix}-%"},
        )
    ).scalar()
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}-{n:04d}"


async def org_name(db: AsyncSession, org_id: uuid.UUID) -> str | None:
    return (await db.execute(text("SELECT legal_name FROM organizations WHERE id = :o"), {"o": org_id})).scalar()


# ================================================================= platform reporting reads (read-only)
_ORG_SUMMARY = (
    "SELECT o.id, o.legal_name, o.workspace_slug, o.public_join_code, o.gstin, o.industry_type, o.state_code, "
    "o.org_status, p.plan_code, o.created_at, o.trial_ends_at, o.owner_user_id, o.plan_id, o.quota_overrides, "
    "o.contact_email, o.contact_phone, o.city, u.email AS owner_email, u.full_name AS owner_name, "
    "(SELECT count(*) FROM org_memberships m WHERE m.org_id = o.id AND m.status = 'ACTIVE') AS member_count"
)
_ORG_FROM = ("FROM organizations o JOIN users u ON u.id = o.owner_user_id "
             "LEFT JOIN platform_subscription_plans p ON p.id = o.plan_id")  # fmt: skip


async def org_page(db: AsyncSession, *, q: str | None, status: str | None, plan_code: str | None,
                   industry: str | None, limit: int, offset: int) -> tuple[list[Any], int]:  # fmt: skip
    where, p = ["true"], {}
    if q:
        where.append("(o.legal_name ILIKE :q OR o.mailing_name ILIKE :q OR o.workspace_slug ILIKE :q "
                     "OR o.gstin ILIKE :q OR o.public_join_code ILIKE :q OR u.email ILIKE :q)")  # fmt: skip
        p["q"] = _like(q.strip())
    if status:
        where.append("o.org_status = :st")
        p["st"] = status
    if plan_code:
        where.append("p.plan_code = :pc")
        p["pc"] = plan_code
    if industry:
        where.append("o.industry_type ILIKE :ind")
        p["ind"] = industry.strip()
    base = f"{_ORG_FROM} WHERE {' AND '.join(where)}"
    return await _page(db, base, _ORG_SUMMARY, "o.created_at DESC, o.id", p, limit, offset)


async def org_row(db: AsyncSession, org_id: uuid.UUID) -> Any | None:
    return (await db.execute(text(f"{_ORG_SUMMARY} {_ORG_FROM} WHERE o.id = :o"), {"o": org_id})).first()  # noqa: S608


async def recent_orgs(db: AsyncSession, n: int = 5) -> list[Any]:
    return list((await db.execute(text(f"{_ORG_SUMMARY} {_ORG_FROM} ORDER BY o.created_at DESC LIMIT :n"),  # noqa: S608
                                  {"n": n})).all())  # fmt: skip


async def org_stats(db: AsyncSession, org_id: uuid.UUID) -> Any:
    return (
        await db.execute(
            text(
                "SELECT "
                "(SELECT count(*) FROM org_memberships m JOIN org_roles r ON r.id = m.role_id WHERE m.org_id = :o "
                " AND m.status = 'ACTIVE' AND r.is_external_collaborator) AS external_count, "
                "(SELECT coalesce(sum(file_size), 0) FROM documents WHERE org_id = :o) AS storage_used_bytes, "
                "(SELECT count(*) FROM vouchers WHERE org_id = :o) AS voucher_count, "
                "(SELECT count(*) FROM period_runs WHERE org_id = :o) AS run_count"
            ),
            {"o": org_id},
        )  # fmt: skip
    ).one()


async def dashboard_counts(db: AsyncSession) -> Any:
    return (
        await db.execute(
            text(
                "SELECT count(*) AS orgs_total, count(*) FILTER (WHERE org_status = 'ACTIVE') AS orgs_active, "
                "count(*) FILTER (WHERE org_status = 'TRIAL') AS orgs_trial, "
                "count(*) FILTER (WHERE org_status = 'SUSPENDED') AS orgs_suspended, "
                "(SELECT count(*) FROM users) AS users_total, "
                "(SELECT coalesce(sum(p.monthly_price_inr), 0) FROM organizations o2 JOIN platform_subscription_plans p "
                " ON p.id = o2.plan_id WHERE o2.org_status = 'ACTIVE') AS mrr_inr, "
                "(SELECT count(*) FROM period_runs WHERE status = 'IN_PROGRESS') AS active_runs, "
                "(SELECT count(*) FROM vouchers WHERE created_at >= date_trunc('day', now())) AS vouchers_today, "
                "(SELECT coalesce(sum(file_size), 0) FROM documents) AS storage_bytes FROM organizations"
            )
        )  # fmt: skip
    ).one()


async def signups_series(db: AsyncSession, days: int = 30) -> list[Any]:
    return list(
        (
            await db.execute(
                text(
                    "SELECT d::date AS date, (SELECT count(*) FROM users u WHERE u.created_at >= d "
                    "AND u.created_at < d + interval '1 day') AS count FROM generate_series("
                    "date_trunc('day', now()) - make_interval(days => :n - 1), date_trunc('day', now()), "
                    "interval '1 day') AS d ORDER BY d"
                ),
                {"n": days},
            )  # fmt: skip
        ).all()
    )


async def org_ids_for_push(db: AsyncSession, org_ids: list[uuid.UUID] | None) -> list[uuid.UUID]:
    if org_ids is None:
        rows = await db.execute(text("SELECT id FROM organizations WHERE org_status <> 'ARCHIVED' ORDER BY created_at"))
    else:
        rows = await db.execute(text("SELECT id FROM organizations WHERE id = ANY(:ids) AND org_status <> 'ARCHIVED'"),
                                {"ids": list(org_ids)})  # fmt: skip
    return list(rows.scalars())


_USER_SUMMARY = (
    "SELECT u.id, u.email, u.full_name, u.is_email_verified, u.mfa_enabled, u.is_suspended, u.last_login_at, "
    "u.created_at, u.mobile, u.professional_reg_no, "
    "(SELECT count(*) FROM org_memberships m WHERE m.user_id = u.id AND m.status = 'ACTIVE') AS org_count"
)


async def user_page(db: AsyncSession, *, q: str | None, suspended: bool | None, limit: int,
                    offset: int) -> tuple[list[Any], int]:  # fmt: skip
    where, p = ["true"], {}
    if q:
        where.append("(u.email ILIKE :q OR u.full_name ILIKE :q OR u.mobile ILIKE :q)")
        p["q"] = _like(q.strip())
    if suspended is not None:
        where.append("u.is_suspended = :s")
        p["s"] = suspended
    return await _page(db, f"FROM users u WHERE {' AND '.join(where)}", _USER_SUMMARY, "u.created_at DESC, u.id",
                       p, limit, offset)  # fmt: skip


async def user_row(db: AsyncSession, user_id: uuid.UUID) -> Any | None:
    return (await db.execute(text(f"{_USER_SUMMARY} FROM users u WHERE u.id = :u"), {"u": user_id})).first()  # noqa: S608


def as_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)
