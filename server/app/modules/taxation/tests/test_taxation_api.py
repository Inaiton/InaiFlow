"""Taxation API: GST summary / GSTR-1 / GSTR-3B / validator / 2B recon, e-invoice + e-way (mock gateway), TDS."""

import json

import pytest

from app.modules.taxation.gst_calc import gstin_checksum_char
from app.modules.taxation.tests.helpers import A, e, ledger, ledgers, voucher
from tests.factories import add_member, set_org

T = f"{A}/taxation"


def gstin(base14: str) -> str:
    return base14 + gstin_checksum_char(base14)


B2B = gstin("29AAACB1234C1Z")
SUPPLIER = gstin("33AAACS5678D1Z")


@pytest.fixture
async def gst_books(client, owner):
    lg = await ledgers(client, owner)
    item = (await client.post(f"{A}/stock-items", json={"name": "Rod", "hsn_sac_code": "72085110", "gst_rate": "18"},
                              headers=owner.headers)).json()["id"]  # fmt: skip
    gd = {g["name"]: g["id"] for g in (await client.get(f"{A}/godowns", headers=owner.headers)).json()}
    b2b = await ledger(client, owner, "SUNDRY_DEBTORS", party_details={"gstin": B2B, "state_code": "29"})
    b2c = await ledger(client, owner, "SUNDRY_DEBTORS", party_details={"state_code": "33", "is_unregistered": True})
    b2cl = await ledger(client, owner, "SUNDRY_DEBTORS", party_details={"state_code": "27", "is_unregistered": True})
    supp = await ledger(
        client, owner, "SUNDRY_CREDITORS", "Acme Steel", party_details={"gstin": SUPPLIER, "state_code": "33"}
    )
    gta = await ledger(client, owner, "SUNDRY_CREDITORS", party_details={"state_code": "33", "is_unregistered": True})
    freight = await ledger(client, owner, "DIRECT_EXPENSES")
    inv = [{"stock_item_id": item, "godown_id": gd["Main Location"], "movement_type": "OUTWARD", "quantity": "10",
            "rate": "1000"}]  # fmt: skip
    sale = await voucher(client, owner, "SALES", "2026-09-10", [e(b2b, "DR", "11800"), e(lg["SALES"], "CR", "10000"),
                         e(lg["IGST_OUT"], "CR", "1800")], party_ledger_id=b2b, inventory=inv)  # fmt: skip
    await voucher(client, owner, "SALES", "2026-09-11", [e(b2c, "DR", "1180"), e(lg["SALES"], "CR", "1000"),
                  e(lg["CGST_OUT"], "CR", "90"), e(lg["SGST_OUT"], "CR", "90")], party_ledger_id=b2c)  # fmt: skip
    await voucher(client, owner, "SALES", "2026-09-12", [e(b2cl, "DR", "236000"), e(lg["SALES"], "CR", "200000"),
                  e(lg["IGST_OUT"], "CR", "36000")], party_ledger_id=b2cl)  # fmt: skip
    await voucher(client, owner, "PURCHASE", "2026-09-05", [e(lg["PURCHASE"], "DR", "50000"), e(lg["CGST_IN"], "DR", "4500"),
                  e(lg["SGST_IN"], "DR", "4500"), e(supp, "CR", "59000")], party_ledger_id=supp,
                  supplier_invoice_no="AS/101", supplier_invoice_date="2026-09-05")  # fmt: skip
    await voucher(client, owner, "PURCHASE", "2026-09-06", [e(freight, "DR", "10000"), e(lg["CGST_IN"], "DR", "250"),
                  e(lg["SGST_IN"], "DR", "250"), e(lg["RCM_PAYABLE"], "CR", "500"), e(gta, "CR", "10000")],
                  party_ledger_id=gta, gst={"reverse_charge": True})  # fmt: skip
    return {"sale": sale, "lg": lg}


async def get(client, owner, path, **params):
    r = await client.get(f"{T}{path}", params=params, headers=owner.headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_summary_gstr1_3b(client, owner, gst_books):
    s = await get(client, owner, "/gst/summary", period="2026-09")
    assert s["outward"] == {
        "taxable": "211000.00",
        "cgst": "90.00",
        "sgst": "90.00",
        "igst": "37800.00",
        "cess": "0.00",
    }
    assert (s["inward_itc"]["cgst"], s["rcm_liability"]["cgst"], s["net_payable"]["cgst"]) == (
        "4750.00",
        "250.00",
        "-4410.00",
    )
    assert s["voucher_count"] == 5
    g1 = await get(client, owner, "/gst/gstr1", period="2026-09")
    assert g1["b2b"][0]["ctin"] == B2B and g1["b2b"][0]["inv"][0]["itms"][0]["itm_det"]["iamt"] == "1800.00"
    assert g1["b2cl"][0]["pos"] == "27" and g1["b2cs"][0]["txval"] == "1000.00"
    assert {h["hsn_sc"] for h in g1["hsn"]} == {"7208", "NA"}
    assert any(i["code"] == "MISSING_HSN" for i in g1["errors"])
    r = await client.get(f"{T}/gst/gstr1/export", params={"period": "2026-09"}, headers=owner.headers)
    exported = json.loads(r.content)
    assert exported["fp"] == "092026" and exported["b2b"][0]["inv"][0]["val"] == 11800
    b3 = await get(client, owner, "/gst/gstr3b", period="2026-09")
    assert b3["sec_3_1"]["osup_det"]["txval"] == "211000.00" and b3["sec_3_1"]["isup_rev"]["camt"] == "250.00"
    assert b3["sec_3_2"]["unreg_details"] == [{"pos": "27", "txval": "200000.00", "iamt": "36000.00"}]
    assert b3["sec_6_1"]["cash_payable"]["igst"] == "28480.00" and b3["sec_6_1"]["rcm_cash_payable"]["cgst"] == "250.00"
    r = await client.get(f"{T}/gst/gstr3b/export", params={"period": "2026-09"}, headers=owner.headers)
    assert json.loads(r.content)["ret_period"] == "092026"
    issues = await get(client, owner, "/gst/validate", period="2026-09")
    assert any(i["code"] == "INVALID_GSTIN" and i["voucher_id"] is None for i in issues)
    bad = await client.get(f"{T}/gst/summary", params={"period": "Sept"}, headers=owner.headers)
    assert bad.status_code == 400


async def test_gstr2b_reconciliation(client, owner, gst_books):
    portal = {"data": {"docdata": {"b2b": [
        {"ctin": SUPPLIER, "trdnm": "ACME", "inv": [{"inum": "as-101", "dt": "06-09-2026", "val": "59000",
                                                     "items": [{"txval": "50000", "cgst": "4500", "sgst": "4500"}]}]},
        {"ctin": B2B, "trdnm": "Other", "inv": [{"inum": "X9", "dt": "01-09-2026", "items": [{"txval": "100", "igst": "18"}]}]},
    ]}}}  # fmt: skip
    r = await client.post(f"{T}/gst/gstr2b/import", params={"period": "2026-09"},
                          files={"file": ("2b.json", json.dumps(portal).encode(), "application/json")}, headers=owner.headers)  # fmt: skip
    assert r.status_code == 201 and r.json()["invoices"] == 2, r.text
    rec = await get(client, owner, "/gst/gstr2b/reconciliation", period="2026-09")
    assert [x["invoice_no"] for x in rec["exact"]] == ["AS/101"]
    assert [x["invoice_no"] for x in rec["missing_in_books"]] == ["X9"] and rec["partial"] == []
    junk = await client.post(f"{T}/gst/gstr2b/import", params={"period": "2026-09"},
                             files={"file": ("2b.json", b"not json", "application/json")}, headers=owner.headers)  # fmt: skip
    assert junk.status_code == 400


async def test_einvoice_and_eway(client, owner, gst_books):
    vid = gst_books["sale"]["id"]
    r = await client.post(f"{T}/einvoice/{vid}/generate", headers=owner.headers)
    assert r.status_code == 400  # fixture org GSTIN fails the checksum
    await set_org(owner.org_id, gstin=gstin("33ABCDE1234F1Z"))
    r = await client.post(f"{T}/einvoice/{vid}/generate", headers=owner.headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["irn"]) == 64 and r.json()["status"] == "GENERATED"
    assert (await client.post(f"{T}/einvoice/{vid}/generate", headers=owner.headers)).status_code == 409
    r = await client.post(
        f"{T}/einvoice/{vid}/cancel", json={"reason_code": "2", "remarks": "Wrong rate"}, headers=owner.headers
    )
    assert r.json()["status"] == "CANCELLED"
    meta = (await client.get(f"{A}/vouchers/{vid}", headers=owner.headers)).json()["gst_metadata"]
    assert meta["einvoice"]["status"] == "CANCELLED"
    eway = {"distance_km": 350, "transport_mode": "ROAD"}
    assert (await client.post(f"{T}/ewaybill/{vid}/generate", json=eway, headers=owner.headers)).status_code == 400
    r = await client.post(
        f"{T}/ewaybill/{vid}/generate", json={**eway, "vehicle_no": "TN38AB1234"}, headers=owner.headers
    )
    assert r.status_code == 200 and len(r.json()["eway_bill_no"]) == 12
    assert len(await get(client, owner, f"/einvoice/{vid}")) == 2


async def test_tds_flow(client, owner):
    lg = await ledgers(client, owner)
    sections = await get(client, owner, "/tds/sections")
    assert any(s["section"] == "194C" for s in sections)
    contractor = await ledger(client, owner, "SUNDRY_CREDITORS", party_details={"pan": "ABCPE1234F"},
                              tax_config={"tax_type": "TDS", "tds_section": "194C"})  # fmt: skip
    r = await client.post(f"{T}/tds/compute", json={"section": "194C", "party_ledger_id": contractor, "amount": "40000",
                                                    "voucher_date": "2026-09-10"}, headers=owner.headers)  # fmt: skip
    assert r.status_code == 200 and r.json()["tds_amount"] == "400.00" and r.json()["rate"] == "1.00"
    job = await ledger(client, owner, "DIRECT_EXPENSES")
    bank = await ledger(client, owner, "BANK_ACCOUNTS")
    await voucher(client, owner, "JOURNAL", "2026-09-10", [e(job, "DR", "40000"), e(contractor, "CR", "39600"),
                  e(lg["TDS_PAYABLE"], "CR", "400")], party_ledger_id=contractor)  # fmt: skip
    rows = await get(client, owner, "/tds/summary", date_from="2026-09-01", date_to="2026-09-30")
    assert [(x["section"], x["tds_amount"], x["amount_paid"], x["deposited"]) for x in rows] == [
        ("194C", "400.00", "40000.00", False)
    ]
    await voucher(client, owner, "PAYMENT", "2026-10-05", [e(lg["TDS_PAYABLE"], "DR", "400"), e(bank, "CR", "400")])
    rows = await get(client, owner, "/tds/summary", date_from="2026-09-01", date_to="2026-09-30")
    assert rows[0]["deposited"] is True
    ch = await get(client, owner, "/tds/challan", month="2026-09")
    assert ch["due_date"] == "2026-10-07" and ch["total"] == "400.00" and ch["by_section"][0]["deductees"] == 1
    r = await client.get(f"{T}/tds/returns/26Q", params={"quarter": "2026-Q2"}, headers=owner.headers)
    assert r.status_code == 200 and b"DD|1|1|1|O|ABCPE1234F" in r.content and b"194C" in r.content
    assert (
        await client.get(f"{T}/tds/returns/24Q", params={"quarter": "2026-Q2"}, headers=owner.headers)
    ).status_code == 400


async def test_taxation_permissions(client, owner):
    op = await add_member(owner.org_id, "OPERATOR")
    assert (await client.get(f"{T}/gst/summary", params={"period": "2026-09"}, headers=op.headers)).status_code == 403
