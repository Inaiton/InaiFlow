"""Voucher API: validation, numbering (incl. concurrency), edit/cancel, period lock, permissions, compute-tax."""

import asyncio

from app.modules.accounts.tests.helpers import A, e, ledger, ledgers, voucher, vtypes
from tests.factories import add_member, org_with_owner


async def _sales(client, owner, day="2026-09-10", amount="1000"):
    lg = await ledgers(client, owner)
    party = await ledger(client, owner, "SUNDRY_DEBTORS")
    return await voucher(client, owner, "SALES", day, [e(party, "DR", amount), e(lg["SALES"], "CR", amount)],
                         party_ledger_id=party)  # fmt: skip


async def test_create_and_sequential_numbers(client, owner):
    v1 = await _sales(client, owner)
    v2 = await _sales(client, owner)
    assert (v1["voucher_number"], v2["voucher_number"]) == ("SI/0001", "SI/0002")
    assert v1["total_amount"] == "1000.00" and len(v1["entries"]) == 2 and v1["status"] == "REGULAR"
    assert v1["created_by_name"] == "Olivia Owner"


async def test_imbalance_and_single_entry_rejected(client, owner):
    lg = await ledgers(client, owner)
    r = await voucher(client, owner, "JOURNAL", "2026-09-10",
                      [e(lg["CASH"], "DR", "100"), e(lg["SALES"], "CR", "99.99")], expect=400)  # fmt: skip
    assert r["error"]["code"] == "DOUBLE_ENTRY_IMBALANCE"
    r = await voucher(client, owner, "JOURNAL", "2026-09-10", [e(lg["CASH"], "DR", "100")], expect=400)
    assert r["error"]["code"] == "VALIDATION_ERROR"


async def test_float_amount_rejected(client, owner):
    lg = await ledgers(client, owner)
    r = await voucher(client, owner, "JOURNAL", "2026-09-10",
                      [e(lg["CASH"], "DR", 100.5), e(lg["SALES"], "CR", "100.5")], expect=422)  # fmt: skip
    assert r["error"]["code"] == "VALIDATION_ERROR"


async def test_books_bounds_and_inactive_ledger(client, owner):
    lg = await ledgers(client, owner)
    await voucher(
        client, owner, "JOURNAL", "2026-03-31", [e(lg["CASH"], "DR", "1"), e(lg["SALES"], "CR", "1")], expect=400
    )
    await voucher(
        client, owner, "JOURNAL", "2027-04-01", [e(lg["CASH"], "DR", "1"), e(lg["SALES"], "CR", "1")], expect=400
    )
    await voucher(client, owner, "JOURNAL", "2027-04-01", [e(lg["CASH"], "DR", "1"), e(lg["SALES"], "CR", "1")],
                  status="POST_DATED")  # fmt: skip
    dead = await ledger(client, owner, "INDIRECT_EXPENSES", is_active=False)
    await voucher(client, owner, "JOURNAL", "2026-09-10", [e(dead, "DR", "1"), e(lg["CASH"], "CR", "1")], expect=400)


async def test_cross_tenant_ledger_and_voucher_404(client, owner):
    other = await org_with_owner(client)
    foreign = (await ledgers(client, other))["CASH"]
    lg = await ledgers(client, owner)
    await voucher(
        client, owner, "JOURNAL", "2026-09-10", [e(foreign, "DR", "1"), e(lg["SALES"], "CR", "1")], expect=400
    )
    v = await _sales(client, owner)
    r = await client.get(f"{A}/vouchers/{v['id']}", headers=other.headers)
    assert r.status_code == 404


async def test_edit_keeps_number_and_logs(client, owner):
    v = await _sales(client, owner)
    body = {"voucher_type_id": v["voucher_type_id"], "voucher_date": "2026-09-11", "party_ledger_id": v["party_ledger_id"],
            "entries": [{"ledger_id": x["ledger_id"], "entry_type": x["entry_type"], "amount": "1500"} for x in v["entries"]],
            "edit_reason": "Rate corrected"}  # fmt: skip
    r = await client.put(f"{A}/vouchers/{v['id']}", json=body, headers=owner.headers)
    assert r.status_code == 200, r.text
    assert r.json()["voucher_number"] == v["voucher_number"] and r.json()["total_amount"] == "1500.00"
    log = (await client.get(f"{A}/vouchers/{v['id']}/edit-log", headers=owner.headers)).json()
    assert [x["action"] for x in log] == ["CREATE", "UPDATE"]
    assert log[1]["reason"] == "Rate corrected" and log[1]["before_diff"] is not None


async def test_cancel_excluded_from_reports(client, owner):
    v = await _sales(client, owner, amount="777")
    r = await client.post(f"{A}/vouchers/{v['id']}/cancel", json={"reason": "Duplicate entry"}, headers=owner.headers)
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED" and r.json()["cancel_reason"] == "Duplicate entry"
    again = await client.post(f"{A}/vouchers/{v['id']}/cancel", json={"reason": "again"}, headers=owner.headers)
    assert again.status_code == 409
    tb = (await client.get(f"{A}/reports/trial-balance", params={"date_from": "2026-04-01", "date_to": "2027-03-31"},
                           headers=owner.headers)).json()  # fmt: skip
    assert tb["total_debit"] == "0.00"
    put = await client.put(f"{A}/vouchers/{v['id']}", json={"voucher_type_id": v["voucher_type_id"],
                           "voucher_date": "2026-09-10", "entries": []}, headers=owner.headers)  # fmt: skip
    assert put.status_code == 409


async def test_period_lock(client, owner):
    old = await _sales(client, owner, day="2026-05-10")
    r = await client.put(f"{A}/settings", json={"books_locked_until": "2026-06-30", "invoice_show_logo": True,
                                                "invoice_terms": None, "invoice_declaration": None,
                                                "invoice_bank_details": None, "invoice_footer": None,
                                                "default_sales_voucher_type_id": None,
                                                "default_purchase_voucher_type_id": None}, headers=owner.headers)  # fmt: skip
    assert r.status_code == 200
    assert (await client.get(f"{A}/settings", headers=owner.headers)).json()["books_locked_until"] == "2026-06-30"
    lg = await ledgers(client, owner)
    r = await voucher(
        client, owner, "JOURNAL", "2026-06-15", [e(lg["CASH"], "DR", "1"), e(lg["SALES"], "CR", "1")], expect=423
    )
    assert r["error"]["code"] == "PERIOD_LOCKED"
    c = await client.post(f"{A}/vouchers/{old['id']}/cancel", json={"reason": "late"}, headers=owner.headers)
    assert c.status_code == 423
    await voucher(client, owner, "JOURNAL", "2026-07-01", [e(lg["CASH"], "DR", "1"), e(lg["SALES"], "CR", "1")])


async def test_concurrent_numbering_is_gap_free(client, owner):
    lg = await ledgers(client, owner)
    vt = await vtypes(client, owner)
    body = {"voucher_type_id": vt["RECEIPT"], "voucher_date": "2026-09-10",
            "entries": [e(lg["CASH"], "DR", "10"), e(lg["SALES"], "CR", "10")]}  # fmt: skip
    rs = await asyncio.gather(*(client.post(f"{A}/vouchers", json=body, headers=owner.headers) for _ in range(6)))
    assert all(r.status_code == 201 for r in rs), [r.text for r in rs]
    assert sorted(r.json()["voucher_number"] for r in rs) == [f"RV/{i:04d}" for i in range(1, 7)]


async def test_idempotent_create(client, owner):
    lg = await ledgers(client, owner)
    vt = await vtypes(client, owner)
    body = {"voucher_type_id": vt["PAYMENT"], "voucher_date": "2026-09-10",
            "entries": [e(lg["ROUND_OFF"], "DR", "5"), e(lg["CASH"], "CR", "5")]}  # fmt: skip
    h = {**owner.headers, "Idempotency-Key": "k-1"}
    r1 = await client.post(f"{A}/vouchers", json=body, headers=h)
    r2 = await client.post(f"{A}/vouchers", json=body, headers=h)
    assert r1.status_code == r2.status_code == 201 and r1.json()["id"] == r2.json()["id"]


async def test_non_accounting_order_without_entries(client, owner):
    party = await ledger(client, owner, "SUNDRY_DEBTORS")
    v = await voucher(client, owner, "SALES_ORDER", "2026-09-10", [], party_ledger_id=party)
    assert v["voucher_number"] == "SO/0001"


async def test_permissions(client, owner):
    op = await add_member(owner.org_id, "OPERATOR")
    r = await client.get(f"{A}/vouchers", headers=op.headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "PERMISSION_DENIED"
    auditor = await add_member(owner.org_id, "AUDITOR", mfa=True)
    for path in (
        "/vouchers",
        "/ledgers",
        "/reports/trial-balance?date_from=2026-04-01&date_to=2026-09-30",
        "/dashboard",
    ):
        assert (await client.get(f"{A}{path}", headers=auditor.headers)).status_code == 403
    acct = await add_member(owner.org_id, "ACCOUNTANT")
    assert (await client.get(f"{A}/vouchers", headers=acct.headers)).status_code == 200
    v = await _sales(client, owner)
    r = await client.post(f"{A}/vouchers/{v['id']}/cancel", json={"reason": "no"}, headers=op.headers)
    assert r.status_code == 403


async def test_compute_tax_intra_and_inter(client, owner):
    lg = await ledgers(client, owner)
    vt = await vtypes(client, owner)
    local = await ledger(
        client, owner, "SUNDRY_DEBTORS", party_details={"state_code": "33", "gstin": "33AAPFU0939F1ZV"}
    )
    away = await ledger(client, owner, "SUNDRY_DEBTORS", party_details={"state_code": "29"})
    line = {"ledger_id": lg["SALES"], "amount": "1001.30", "gst_rate": "18", "hsn_sac_code": "7208"}
    r = await client.post(f"{A}/vouchers/compute-tax", json={"voucher_type_id": vt["SALES"], "voucher_date": "2026-09-10",
                                                             "party_ledger_id": local, "lines": [line]}, headers=owner.headers)  # fmt: skip
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["tax_split"], out["cgst"], out["sgst"], out["igst"]) == ("INTRA", "90.12", "90.12", "0.00")
    assert (out["invoice_total"], out["round_off"]) == ("1182.00", "0.46")
    sides = {(x["ledger_id"], x["entry_type"]): x["amount"] for x in out["suggested_entries"]}
    assert sides[(local, "DR")] == "1182.00" and sides[(lg["ROUND_OFF"], "CR")] == "0.46"
    assert sides[(lg["CGST_OUT"], "CR")] == "90.12"
    # the suggestion posts as a balanced voucher
    await voucher(client, owner, "SALES", "2026-09-10", out["suggested_entries"], party_ledger_id=local)
    r = await client.post(f"{A}/vouchers/compute-tax", json={"voucher_type_id": vt["PURCHASE"], "voucher_date": "2026-09-10",
                                                             "party_ledger_id": away,
                                                             "lines": [{**line, "ledger_id": lg["PURCHASE"]}]},
                          headers=owner.headers)  # fmt: skip
    out = r.json()
    assert out["tax_split"] == "INTER" and out["igst"] == "180.23"
    assert {(x["entry_type"]) for x in out["suggested_entries"] if x["ledger_id"] == lg["IGST_IN"]} == {"DR"}


async def test_voucher_print_pdf(client, owner):
    v = await _sales(client, owner)
    r = await client.get(f"{A}/vouchers/{v['id']}/print", headers=owner.headers)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
