"""Org-creation seeding for payroll: ``payroll_settings`` mapped to the system payroll ledgers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.errors import NotFoundError
from app.modules.accounts import interface as accounts
from app.modules.organization import interface as organization
from app.modules.payroll.models import PayrollSettings
from app.modules.platform.interface import get_config

LEDGER_MAP = {
    "salary_payable_ledger_id": "SALARY_PAYABLE",
    "direct_wages_ledger_id": "DIRECT_WAGES",
    "admin_salary_ledger_id": "ADMIN_SALARIES",
    "employer_contrib_ledger_id": "EMPLOYER_PF_ESIC",
    "epf_payable_ledger_id": "EPF_PAYABLE",
    "esic_payable_ledger_id": "ESIC_PAYABLE",
    "pt_payable_ledger_id": "PT_PAYABLE",
    "tds_payable_ledger_id": "SALARY_TDS_PAYABLE",
}


async def seed_org_payroll(db: AsyncSession, ctx: TenantContext) -> None:
    org = await organization.get_org_brief(db, ctx.org_id)
    if org is None:
        raise NotFoundError()
    ids = await accounts.get_ledger_ids_by_code(db, ctx, list(LEDGER_MAP.values()))
    pt_states = (await get_config(db, "PAYROLL_STATUTORY", "PT_SLABS"))["states"]
    db.add(PayrollSettings(org_id=ctx.org_id, pt_state_code=org.state_code if org.state_code in pt_states else None,
                           working_days_basis="CALENDAR", **{col: ids[code] for col, code in LEDGER_MAP.items()}))  # fmt: skip
    await db.flush()
