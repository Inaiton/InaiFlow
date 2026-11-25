"""Shared accounts helpers: org brief / settings, period-lock and books-bounds guards, output builders."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.errors import NotFoundError, PeriodLockedError, ValidationFailedError
from app.core.fy import fy_for_date
from app.modules.accounts.ledger_math import Chart, split
from app.modules.accounts.models import Ledger
from app.modules.accounts.schemas import LedgerOut
from app.modules.organization import interface as organization
from app.modules.organization.interface import OrgBrief


async def org_brief(db: AsyncSession, ctx: TenantContext) -> OrgBrief:
    org = await organization.get_org_brief(db, ctx.org_id)
    if org is None:
        raise NotFoundError()
    return org


def locked_until(org: OrgBrief) -> date | None:
    raw = (org.accounts_settings or {}).get("books_locked_until")
    return date.fromisoformat(raw) if isinstance(raw, str) and raw else None


def assert_period_open(org: OrgBrief, *dates: date) -> None:
    lock = locked_until(org)
    for d in dates:
        if lock is not None and d <= lock:
            raise PeriodLockedError(f"The books are locked up to {lock.isoformat()}",
                                    details={"books_locked_until": lock.isoformat(), "voucher_date": d.isoformat()})  # fmt: skip


def assert_in_books(org: OrgBrief, d: date, *, status: str, today: date | None = None) -> None:
    """Voucher dates must be >= books_beginning_from and inside the current FY (POST_DATED: up to the next FY)."""
    if d < org.books_beginning_from:
        raise ValidationFailedError(
            f"Voucher date is before the books beginning date {org.books_beginning_from.isoformat()}",
            details={"field": "voucher_date"},
        )
    today = today or date.today()
    limit = fy_for_date(today, org.fy_begins_from).end
    if status == "POST_DATED":
        limit = fy_for_date(limit + timedelta(days=1), org.fy_begins_from).end
    if d > limit:
        raise ValidationFailedError(f"Voucher date is after the end of the financial year ({limit.isoformat()})",
                                    details={"field": "voucher_date"})  # fmt: skip


def ledger_out(lg: Ledger, chart: Chart, closing_signed: Decimal) -> LedgerOut:
    grp = chart.groups[lg.group_id]
    amount, kind = split(closing_signed)
    return LedgerOut(
        id=lg.id, group_id=lg.group_id, group_name=grp.name, nature=grp.nature, name=lg.name, alias=lg.alias,
        system_code=lg.system_code, currency_code=lg.currency_code, opening_balance=lg.opening_balance,
        opening_balance_type=lg.opening_balance_type, maintain_bill_by_bill=lg.maintain_bill_by_bill,
        default_credit_days=lg.default_credit_days, credit_limit=lg.credit_limit,
        party_details=lg.party_details or None, tax_config=lg.tax_config or None,
        interest_config=lg.interest_config or None, is_active=lg.is_active, closing_balance=amount,
        closing_balance_type=kind, created_at=lg.created_at,
    )  # fmt: skip


def snapshot(obj: Any) -> dict[str, Any]:
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


def as_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
