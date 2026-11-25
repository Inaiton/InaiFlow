"""Public API of the platform module (effective-dated configs, plans).

``get_config(db, "PAYROLL_STATUTORY", "EPF", on_date=voucher_date)`` returns the payload of the version in
force on that date (falls back to the bundled seed when the row is missing, so fresh test DBs work).
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.modules.platform import repository as repo
from app.seeds import PLANS, config_rows

MODULE_KEYS = ("accounts", "payroll", "operations", "documents", "tally_xml_sync", "irp_einvoice")


def _seed_payload(category: str, key: str) -> dict | None:
    for row in config_rows():
        if row["category"] == category and row["key"] == key:
            return copy.deepcopy(row["payload"])
    return None


async def get_config(db: AsyncSession, category: str, key: str = "default", on_date: date | None = None) -> dict:
    payload = await repo.config_payload(db, category, key, on_date)
    if payload is None:
        payload = _seed_payload(category, key)
    if payload is None:
        raise NotFoundError(f"Configuration {category}/{key} not found")
    return payload


async def list_configs(db: AsyncSession, category: str, on_date: date | None = None) -> list[tuple[str, dict]]:
    keys = await repo.config_keys(db, category)
    if not keys:
        return [(r["key"], copy.deepcopy(r["payload"])) for r in config_rows() if r["category"] == category]
    return [(k, await get_config(db, category, k, on_date)) for k in keys]


@dataclass(frozen=True, slots=True)
class PlanDTO:
    id: uuid.UUID | None
    plan_code: str
    name: str
    max_internal_seats: int
    max_external_collaborators: int
    max_storage_gb: int
    enabled_modules: dict[str, bool]
    monthly_price_inr: Decimal


def _dto(plan: Any) -> PlanDTO:
    return PlanDTO(plan.id, plan.plan_code, plan.name, plan.max_internal_seats, plan.max_external_collaborators,
                   plan.max_storage_gb, dict(plan.enabled_modules or {}), Decimal(plan.monthly_price_inr))  # fmt: skip


async def get_plan(db: AsyncSession, plan_id: uuid.UUID | None) -> PlanDTO | None:
    if plan_id is None:
        return None
    plan = await repo.plan_by_id(db, plan_id)
    return _dto(plan) if plan else None


async def get_plan_by_code(db: AsyncSession, code: str) -> PlanDTO | None:
    plan = await repo.plan_by_code(db, code)
    if plan:
        return _dto(plan)
    for p in PLANS:
        if p["plan_code"] == code:
            return PlanDTO(None, code, p["name"], p["max_internal_seats"], p["max_external_collaborators"],
                           p["max_storage_gb"], dict(p["enabled_modules"]), Decimal(p["monthly_price_inr"]))  # fmt: skip
    return None


def effective_limits(plan: PlanDTO | None, quota_overrides: dict | None) -> dict[str, Any]:
    """Plan limits with per-org ``quota_overrides`` applied (keys: max_internal_seats,
    max_external_collaborators, max_storage_gb, enabled_modules)."""
    q = quota_overrides or {}
    base_modules = dict.fromkeys(MODULE_KEYS, False)
    if plan:
        base_modules.update({k: bool(v) for k, v in plan.enabled_modules.items() if k in MODULE_KEYS})
    else:
        base_modules.update(dict.fromkeys(("accounts", "payroll", "operations", "documents"), True))
    base_modules.update({k: bool(v) for k, v in (q.get("enabled_modules") or {}).items() if k in MODULE_KEYS})
    return {
        "max_internal_seats": int(q.get("max_internal_seats", plan.max_internal_seats if plan else 5)),
        "max_external_collaborators": int(
            q.get("max_external_collaborators", plan.max_external_collaborators if plan else 2)
        ),
        "max_storage_gb": int(q.get("max_storage_gb", plan.max_storage_gb if plan else 2)),
        "enabled_modules": {k: bool(v) for k, v in base_modules.items()},
    }
