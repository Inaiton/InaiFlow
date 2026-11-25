"""Org-creation seeding for accounts: 28 groups, default ledgers, voucher types, system godowns, base currency."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.core.errors import NotFoundError
from app.modules.accounts.models import AccountGroup, Currency, Godown, Ledger, VoucherType
from app.modules.organization import interface as organization
from app.modules.platform.interface import get_config
from app.seeds.default_ledgers import INDUSTRY_LEDGERS
from app.seeds.states import UT_WITHOUT_LEGISLATURE

CURRENCY_NAMES = {"INR": "Indian Rupee", "USD": "US Dollar", "EUR": "Euro", "GBP": "Pound Sterling"}


async def seed_org_accounts(db: AsyncSession, ctx: TenantContext, industry_type: str) -> dict[str, uuid.UUID]:
    """Returns ledger ids by system_code."""
    org = await organization.get_org_brief(db, ctx.org_id)
    if org is None:
        raise NotFoundError()
    groups_cfg = (await get_config(db, "ACCOUNT_GROUPS"))["groups"]
    group_ids: dict[str, uuid.UUID] = {}
    for g in sorted(groups_cfg, key=lambda g: g["parent"] is not None):  # primaries first
        row = AccountGroup(org_id=ctx.org_id, name=g["name"], nature=g["nature"],
                           parent_group_id=group_ids.get(g["parent"]) if g["parent"] else None,
                           affects_gross_profit=g["affects_gross_profit"], is_system_group=True,
                           system_code=g["system_code"])  # fmt: skip
        db.add(row)
        await db.flush()
        group_ids[g["system_code"]] = row.id

    ledgers_cfg = await get_config(db, "DEFAULT_LEDGERS")
    sgst_label = "UTGST" if org.state_code in UT_WITHOUT_LEGISLATURE else "SGST"
    extra = [lg for key, items in INDUSTRY_LEDGERS.items() if key in industry_type.lower() for lg in items]
    ledger_ids: dict[str, uuid.UUID] = {}
    seen: set[str] = set()
    for lg in [*ledgers_cfg["ledgers"], *extra]:
        name = lg["name"].replace("{SGST}", sgst_label)
        if name in seen:
            continue
        seen.add(name)
        row = Ledger(org_id=ctx.org_id, group_id=group_ids[lg["group"]], name=name, system_code=lg.get("system_code"),
                     currency_code=org.base_currency_code, tax_config=lg.get("tax_config"))  # fmt: skip
        db.add(row)
        await db.flush()
        if row.system_code:
            ledger_ids[row.system_code] = row.id

    for vt in (await get_config(db, "VOUCHER_TYPES"))["voucher_types"]:
        db.add(VoucherType(org_id=ctx.org_id, name=vt["name"], base_type=vt["base_type"],
                           is_accounting=vt["is_accounting"], shortcut=vt.get("shortcut"), is_system=True,
                           prefix=vt.get("prefix", ""), suffix=vt.get("suffix", ""), zero_padding=4, next_number=1))  # fmt: skip
    for gd in ledgers_cfg["godowns"]:
        db.add(Godown(org_id=ctx.org_id, name=gd["name"], godown_type=gd["godown_type"], is_system=True,
                      system_code=gd["system_code"]))  # fmt: skip
    db.add(Currency(org_id=ctx.org_id, code=org.base_currency_code, symbol=org.base_currency_symbol,
                    name=CURRENCY_NAMES.get(org.base_currency_code, org.base_currency_code), decimal_places=2))  # fmt: skip
    await db.flush()
    return ledger_ids
