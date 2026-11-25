"""Seeded mini-ledger: TB balances, P&L / BS / cash flow tie out; ageing, stock, exports, dashboard, Tally XML."""

from decimal import Decimal

import pytest

from app.modules.accounts.tests.helpers import A, e, groups, ledger, ledgers, voucher

D = Decimal
FY = {"date_from": "2026-04-01", "date_to": "2027-03-31"}


@pytest.fixture
async def books(client, owner):
    lg = await ledgers(client, owner)
    capital = await ledger(client, owner, "CAPITAL_ACCOUNT", "Owner Capital", opening_balance="100000",
                           opening_balance_type="CR")  # fmt: skip
    r = await client.patch(f"{A}/ledgers/{lg['CASH']}", json={"group_id": (await groups(client, owner))["CASH_IN_HAND"],
                           "name": "Cash", "opening_balance": "100000", "opening_balance_type": "DR"}, headers=owner.headers)  # fmt: skip
    assert r.status_code == 200, r.text
    bank = await ledger(client, owner, "BANK_ACCOUNTS", "HDFC Current")
    supplier = await ledger(client, owner, "SUNDRY_CREDITORS", "Acme Steel", party_details={"msme_type": "MICRO"})
    customer = await ledger(client, owner, "SUNDRY_DEBTORS", "Buyer Ltd", default_credit_days=30)
    rent = await ledger(client, owner, "INDIRECT_EXPENSES", "Rent")
    gd = {g["name"]: g["id"] for g in (await client.get(f"{A}/godowns", headers=owner.headers)).json()}
    item = (await client.post(f"{A}/stock-items", json={"name": "Steel Rod", "hsn_sac_code": "72085110", "gst_rate": "18"},
                              headers=owner.headers)).json()["id"]  # fmt: skip
    main = gd["Main Location"]
    await voucher(client, owner, "PURCHASE", "2026-05-02",
                  [e(lg["PURCHASE"], "DR", "50000"), e(lg["CGST_IN"], "DR", "4500"), e(lg["SGST_IN"], "DR", "4500"),
                   e(supplier, "CR", "59000")], party_ledger_id=supplier, supplier_invoice_no="AS/101",
                  inventory=[{"stock_item_id": item, "godown_id": main, "movement_type": "INWARD", "quantity": "100",
                              "rate": "500"}])  # fmt: skip
    await voucher(client, owner, "SALES", "2026-05-10",
                  [e(customer, "DR", "118000"), e(lg["SALES"], "CR", "100000"), e(lg["CGST_OUT"], "CR", "9000"),
                   e(lg["SGST_OUT"], "CR", "9000")], party_ledger_id=customer,
                  inventory=[{"stock_item_id": item, "godown_id": main, "movement_type": "OUTWARD", "quantity": "60",
                              "rate": "1666.6667", "amount": "100000"}])  # fmt: skip
    await voucher(client, owner, "RECEIPT", "2026-05-20", [e(bank, "DR", "100000", instrument_no="445566"),
                                                           e(customer, "CR", "100000")])  # fmt: skip
    await voucher(client, owner, "PAYMENT", "2026-05-25", [e(rent, "DR", "10000"), e(lg["CASH"], "CR", "10000")])
    return {"lg": lg, "capital": capital, "bank": bank, "supplier": supplier, "customer": customer, "item": item}


async def get(client, owner, path, **params):
    r = await client.get(f"{A}{path}", params=params, headers=owner.headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_trial_balance_balances(client, owner, books):
    tb = await get(client, owner, "/reports/trial-balance", **FY)
    assert tb["total_debit"] == tb["total_credit"] == "277000.00" and tb["difference"] == "0.00"
    led = await get(client, owner, "/reports/trial-balance", **FY, mode="ledger")
    assert all(r["kind"] == "LEDGER" for r in led["rows"]) and led["total_debit"] == "277000.00"


async def test_pnl_bs_cash_flow_tie_out(client, owner, books):
    pl = await get(client, owner, "/reports/profit-loss", **FY)
    assert (pl["opening_stock"], pl["closing_stock"]) == ("0.00", "20000.00")
    assert pl["gross_profit"] == "70000.00" and pl["net_profit"] == "60000.00"
    bs = await get(client, owner, "/reports/balance-sheet", as_of="2027-03-31")
    assert bs["total_assets"] == bs["total_liabilities"] == "228000.00" and bs["difference"] == "0.00"
    funds = bs["equity_and_liabilities"][0]
    assert any(c["label"].startswith("Profit & Loss") and c["amount"] == "60000.00" for c in funds["children"])
    cf = await get(client, owner, "/reports/cash-flow", **FY)
    total = sum(D(s["amount"]) for k in ("operating", "investing", "financing") for s in cf[k])
    assert D(cf["net_change"]) == total == D("90000")
    assert (cf["opening_cash"], cf["closing_cash"]) == ("100000.00", "190000.00")
    ratios = {r["key"]: r["value"] for r in await get(client, owner, "/reports/ratios", **FY)}
    assert ratios["gross_margin_pct"] == "70.00" and ratios["net_margin_pct"] == "60.00" and len(ratios) == 8


async def test_statement_bills_and_ageing(client, owner, books):
    st = await get(client, owner, f"/ledgers/{books['customer']}/statement", **FY)
    assert [x["running_balance"] for x in st["lines"]] == ["118000.00", "18000.00"]
    assert (
        st["closing_balance"] == "18000.00"
        and st["closing_type"] == "DR"
        and st["lines"][0]["particulars"] == "Sales (as per details)"
    )
    bills = await get(client, owner, f"/ledgers/{books['customer']}/bills", as_of="2026-07-01")
    assert len(bills) == 1 and bills[0]["pending"] == "18000.00" and bills[0]["overdue_days"] == 22
    ag = await get(client, owner, "/reports/ageing", kind="PAYABLE", as_of="2026-07-10")
    row = next(r for r in ag["rows"] if r["ledger_id"] == books["supplier"])
    assert row["buckets"]["61-90"] == "59000.00" and row["msme_overdue"] is True
    exc = {x["kind"] for x in await get(client, owner, "/utilities/exceptions")}
    assert "MSME_OVERDUE" in exc and "UNRECONCILED_BANK" in exc


async def test_stock_and_movements(client, owner, books):
    rows = {r["stock_item_id"]: r for r in await get(client, owner, "/inventory/stock-summary")}
    assert (rows[books["item"]]["quantity"], rows[books["item"]]["value"]) == ("40.00", "20000.00")
    mv = await get(client, owner, f"/inventory/items/{books['item']}/movements", **FY)
    assert [m["balance_qty"] for m in mv] == ["100.00", "40.00"] and mv[1]["rate"] == "500.00"


async def test_exports_daybook_dashboard_tally(client, owner, books):
    r = await client.get(f"{A}/reports/trial-balance/export", params={"format": "csv", **FY}, headers=owner.headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and b"277000.00" in r.content
    r = await client.get(f"{A}/reports/profit-loss/export", params={"format": "pdf", **FY}, headers=owner.headers)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    r = await client.get(f"{A}/reports/balance-sheet/export", params={"format": "csv"}, headers=owner.headers)
    assert r.status_code == 400
    db = await get(client, owner, "/reports/day-book", **FY)
    assert db["total"] == 4
    dash = await get(client, owner, "/dashboard")
    assert [k["key"] for k in dash["kpis"]][:3] == ["cash_bank", "receivables", "payables"]
    assert dash["kpis"][0]["value"] == "190000.00" and len(dash["cash_flow"]) == 6 and len(dash["recent_vouchers"]) == 4
    r = await client.get(f"{A}/utilities/tally-export", params=FY, headers=owner.headers)
    assert r.status_code == 200 and b"<ENVELOPE>" in r.content and b"VOUCHERNUMBER" in r.content
    assert b'<LEDGER NAME="Owner Capital"' in r.content
    batch = await get(client, owner, "/reports/batch-costing", **FY)
    assert batch == []
