"""Org-creation seeding for documents: FY root, Master Library tree, current month folders, system templates.

Folder names: FY root ``"FY 2026-27"``; month ``"09 - September 2026"`` (``app.core.fy.month_folder_name``);
all system folders are ``is_system_locked = true`` with a ``system_kind``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.errors import NotFoundError
from app.core.fy import fy_for_date, month_folder_name, month_start
from app.modules.documents.models import DocFolder, DocTemplate
from app.modules.organization import interface as organization
from app.modules.platform.interface import get_config, list_configs
from app.seeds.folder_templates import DEFAULT_MONTHLY_RULE

MONTH_KINDS = {"BILLS": "bills_id", "OPERATIONS": "operations_id", "PAYROLL": "payroll_id"}


@dataclass
class MonthFolders:
    month_folder_id: uuid.UUID
    fy_folder_id: uuid.UUID
    bills_id: uuid.UUID
    operations_id: uuid.UUID
    payroll_id: uuid.UUID
    custom: dict[str, uuid.UUID] = field(default_factory=dict)
    created: int = 0  # folders created by this call


async def _get_or_create(
    db: AsyncSession, ctx: TenantContext, parent_id: uuid.UUID | None, name: str, *, kind: str,
    fy_label: str | None = None, month: date | None = None,
) -> tuple[uuid.UUID, bool]:  # fmt: skip
    cond = DocFolder.parent_folder_id.is_(None) if parent_id is None else DocFolder.parent_folder_id == parent_id
    existing = (
        await db.execute(select(DocFolder.id).where(DocFolder.org_id == ctx.org_id, cond, DocFolder.name == name))
    ).scalar()
    if existing:
        return existing, False
    folder = DocFolder(org_id=ctx.org_id, parent_folder_id=parent_id, name=name, system_kind=kind,
                       fy_label=fy_label, month_date=month, is_system_locked=True)  # fmt: skip
    db.add(folder)
    await db.flush()
    return folder.id, True


async def _custom_monthly(db: AsyncSession, ctx: TenantContext) -> list[str]:
    rows = await db.execute(
        select(DocTemplate.content_schema).where(
            DocTemplate.org_id == ctx.org_id, DocTemplate.template_type == "MONTHLY_FOLDER_RULE"
        )
    )
    names: list[str] = []
    for schema in rows.scalars():
        for item in (schema or {}).get("custom", []) or []:
            name = item.get("name") if isinstance(item, dict) else str(item)
            if name and name not in names:
                names.append(name)
    return names


async def ensure_month_folders(db: AsyncSession, ctx: TenantContext, month: date) -> MonthFolders:
    """Idempotent: ``/FY …/MM - Month YYYY/{Bills & Vouchers, Operations & Production Runs, Payroll & Statutory
    Challans, custom…}``."""
    org = await organization.get_org_brief(db, ctx.org_id)
    if org is None:
        raise NotFoundError()
    m = month_start(month)
    fy = fy_for_date(m, org.fy_begins_from)
    created = 0
    fy_id, c = await _get_or_create(db, ctx, None, fy.label, kind="FY_ROOT", fy_label=fy.label)
    created += c
    month_id, c = await _get_or_create(db, ctx, fy_id, month_folder_name(m), kind="MONTH", fy_label=fy.label, month=m)
    created += c
    ids: dict[str, uuid.UUID] = {}
    monthly = await get_config(db, "FOLDER_TEMPLATES", "MONTHLY")
    for sub in monthly.get("subfolders", DEFAULT_MONTHLY_RULE["subfolders"]):
        fid, c = await _get_or_create(
            db, ctx, month_id, sub["name"], kind=sub["system_kind"], fy_label=fy.label, month=m
        )
        created += c
        ids[sub["system_kind"]] = fid
    custom: dict[str, uuid.UUID] = {}
    for name in await _custom_monthly(db, ctx):
        fid, c = await _get_or_create(db, ctx, month_id, name, kind="CUSTOM", fy_label=fy.label, month=m)
        created += c
        custom[name] = fid
    return MonthFolders(month_id, fy_id, ids["BILLS"], ids["OPERATIONS"], ids["PAYROLL"], custom, created)


async def seed_org_documents(db: AsyncSession, ctx: TenantContext) -> MonthFolders:
    from datetime import UTC, datetime

    lib = await get_config(db, "FOLDER_TEMPLATES", "MASTER_LIBRARY")
    root_id, _ = await _get_or_create(db, ctx, None, lib["name"], kind=lib["system_kind"])
    for child in lib.get("children", []):
        await _get_or_create(db, ctx, root_id, child["name"], kind=child["system_kind"])
    for key, payload in await list_configs(db, "DOC_REPORT_TEMPLATES"):
        db.add(DocTemplate(org_id=ctx.org_id, template_type="REPORT_DOC", name=payload["name"],
                           description=payload.get("description"), system_key=key, is_system_default=True,
                           content_schema={"blocks": payload["blocks"]}, created_by=ctx.user_id))  # fmt: skip
    db.add(DocTemplate(org_id=ctx.org_id, template_type="MONTHLY_FOLDER_RULE", name="Monthly folders",
                       description="System monthly subfolders; add custom names under 'custom'.",
                       system_key="MONTHLY", is_system_default=True, content_schema=dict(DEFAULT_MONTHLY_RULE),
                       created_by=ctx.user_id))  # fmt: skip
    await db.flush()
    return await ensure_month_folders(db, ctx, datetime.now(UTC).date())
