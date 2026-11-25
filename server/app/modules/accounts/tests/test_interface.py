"""accounts.interface functions used by payroll (S3) and operations (S4)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.core.context import TenantContext
from app.core.db import get_sessionmaker, set_tenant_scope
from app.core.errors import DoubleEntryImbalanceError, NotFoundError
from app.modules.accounts import interface as acc
from app.modules.accounts.tests.helpers import A, ledger

D = Decimal


async def _scoped(owner):
    s = get_sessionmaker()()
    await s.begin()
    await set_tenant_scope(s, owner.org_id, owner.user_id)
    return s


async def test_post_system_voucher_cost_centres_and_run_links(client, owner):
    run_id, other_run = uuid.uuid4(), uuid.uuid4()
    ctx = TenantContext.system(owner.org_id)
    s = await _scoped(owner)
    try:
        cc = await acc.create_cost_centre(s, ctx, name="Component 1 - Sept 2026", linked_period_run_id=run_id)
        assert await acc.create_cost_centre(s, ctx, name="Component 1 - Sept 2026", linked_period_run_id=run_id) == cc
        cc2 = await acc.create_cost_centre(s, ctx, name="Component 1 - Sept 2026", linked_period_run_id=other_run)
        assert cc2 != cc
        codes = await acc.get_ledger_ids_by_code(s, ctx, ["DIRECT_WAGES", "SALARY_PAYABLE", "CASH", "SALES"])
        vid = await acc.post_system_voucher(
            s, ctx, base_type="PAYROLL", voucher_date=date(2026, 9, 30), narration="Payroll Sept 2026",
            entries=[acc.SystemEntry(codes["DIRECT_WAGES"], "DR", D("600"), cost_centre_id=cc),
                     acc.SystemEntry(codes["DIRECT_WAGES"], "DR", D("400"), cost_centre_id=None),
                     acc.SystemEntry(codes["SALARY_PAYABLE"], "CR", D("1000"))])  # fmt: skip
        runs = await acc.list_vouchers_for_run(s, ctx, run_id)
        assert [v.id for v in runs] == [vid] and runs[0].base_type == "PAYROLL" and len(runs[0].entries) == 3
        other = await acc.post_system_voucher(s, ctx, base_type="JOURNAL", voucher_date=date(2026, 9, 30), narration=None,
                                              entries=[acc.SystemEntry(codes["CASH"], "DR", D("5")),
                                                       acc.SystemEntry(codes["SALES"], "CR", D("5"))])  # fmt: skip
        await acc.link_voucher_to_run(s, ctx, voucher_id=other, run_id=other_run)
        assert [v.id for v in await acc.list_vouchers_for_run(s, ctx, other_run)] == [other]
        assert await acc.ledger_balance(s, ctx, codes["SALARY_PAYABLE"]) == D("-1000")
        with pytest.raises(DoubleEntryImbalanceError):
            await acc.post_system_voucher(s, ctx, base_type="JOURNAL", voucher_date=date(2026, 9, 30), narration=None,
                                          entries=[acc.SystemEntry(codes["CASH"], "DR", D("5")),
                                                   acc.SystemEntry(codes["SALES"], "CR", D("4"))])  # fmt: skip
    finally:
        await s.rollback()
        await s.close()


async def test_stock_item_valuation_and_resource_names(client, owner):
    item = (await client.post(f"{A}/stock-items", json={"name": "Bar", "opening_qty": "10", "opening_rate": "12.5"},
                              headers=owner.headers)).json()["id"]  # fmt: skip
    bank = await ledger(client, owner, "BANK_ACCOUNTS", "Axis Payroll A/c")
    ctx = TenantContext.system(owner.org_id)
    s = await _scoped(owner)
    try:
        dto = await acc.get_stock_item(s, ctx, uuid.UUID(item))
        assert dto.name == "Bar" and dto.opening_qty == D("10")
        val = await acc.stock_valuation(s, ctx, uuid.UUID(item))
        assert (val.quantity, val.value) == (D("10"), D("125"))
        names = await acc.resource_names(s, ctx, "LEDGER", [uuid.UUID(bank)])
        assert names == {uuid.UUID(bank): "Axis Payroll A/c"}
        brief = await acc.get_ledger(s, ctx, uuid.UUID(bank))
        assert brief.is_bank and brief.primary_group_code == "CURRENT_ASSETS"
        with pytest.raises(NotFoundError):
            await acc.get_stock_item(s, ctx, uuid.uuid4())
    finally:
        await s.rollback()
        await s.close()


async def test_stock_item_rejects_foreign_storage_key(client, owner):
    other = f"org/{uuid.uuid4()}/2026/09/{uuid.uuid4()}/secret.pdf"
    r = await client.post(
        f"{A}/stock-items", json={"name": "Leak", "diagram_storage_key": other}, headers=owner.headers
    )
    assert r.status_code == 400
