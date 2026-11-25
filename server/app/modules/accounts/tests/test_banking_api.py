"""Banking: statement import + auto-match + duplicates, BRS view, manual reconcile/unmatch/ignore, cheques."""

from app.modules.accounts.tests.helpers import A, e, ledger, ledgers, voucher

CSV = b"""Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
11/09/26,CHQ PAID ACME,000101,11/09/26,"5,000.00",,"95,000.00"
12/09/26,BANK CHARGES,,12/09/26,118.00,,"94,882.00"
"""


async def test_import_auto_match_and_reconcile(client, owner):
    lg = await ledgers(client, owner)
    bank = await ledger(client, owner, "BANK_ACCOUNTS", party_details={"bank_account": "5010001", "ifsc": "HDFC0001"})
    r = await client.post(f"{A}/banking/cheque-books", json={"bank_ledger_id": bank, "from_number": "000101",
                                                             "to_number": "000150"}, headers=owner.headers)  # fmt: skip
    assert r.status_code == 201, r.text
    v = await voucher(client, owner, "PAYMENT", "2026-09-10", [e(lg["PURCHASE"], "DR", "5000"),
                      e(bank, "CR", "5000", instrument_no="000101", instrument_date="2026-09-10")])  # fmt: skip
    other = await voucher(
        client, owner, "PAYMENT", "2026-09-12", [e(lg["ROUND_OFF"], "DR", "200"), e(bank, "CR", "200")]
    )
    books = (await client.get(f"{A}/banking/cheque-books", headers=owner.headers)).json()
    assert books[0]["next_number"] == "000102" and books[0]["used_count"] == 1

    files = {"file": ("hdfc.csv", CSV, "text/csv")}
    r = await client.post(f"{A}/banking/{bank}/statements/import", files=files, headers=owner.headers)
    assert r.status_code == 201, r.text
    assert r.json() | {"import_id": None} == {"import_id": None, "format": "CSV", "lines_imported": 2, "auto_matched": 1,
                                              "duplicates_skipped": 0}  # fmt: skip
    again = (await client.post(f"{A}/banking/{bank}/statements/import", files=files, headers=owner.headers)).json()
    assert again["duplicates_skipped"] == 2 and again["lines_imported"] == 0

    rec = (
        await client.get(f"{A}/banking/{bank}/reconciliation", params={"as_of": "2026-09-30"}, headers=owner.headers)
    ).json()
    assert rec["balance_as_per_books"] == "5200.00" and rec["books_type"] == "CR"
    assert rec["amounts_not_reflected_in_bank"] == "-200.00" and rec["balance_as_per_bank"] == "-5000.00"
    assert [x["voucher_id"] for x in rec["entries"]] == [other["id"]]
    assert [x["description"] for x in rec["statement_lines"]] == ["BANK CHARGES"]

    lines = (await client.get(f"{A}/banking/{bank}/statement-lines", headers=owner.headers)).json()["items"]
    matched = next(x for x in lines if x["status"] == "MATCHED")
    pending = next(x for x in lines if x["status"] == "UNMATCHED")
    r = await client.post(f"{A}/banking/statement-lines/{matched['id']}/unmatch", headers=owner.headers)
    assert r.status_code == 200 and r.json()["status"] == "UNMATCHED"
    entry = next(x for x in (await client.get(f"{A}/vouchers/{v['id']}", headers=owner.headers)).json()["entries"]
                 if x["ledger_id"] == bank)  # fmt: skip
    assert entry["bank_reconciliation_date"] is None
    r = await client.post(f"{A}/banking/statement-lines/{matched['id']}/match", json={"entry_id": entry["id"]},
                          headers=owner.headers)  # fmt: skip
    assert r.status_code == 200 and r.json()["matched_entry_id"] == entry["id"]
    assert (await client.post(f"{A}/banking/statement-lines/{pending['id']}/ignore", headers=owner.headers)).json()[
        "status"
    ] == "IGNORED"

    oentry = next(x for x in (await client.get(f"{A}/vouchers/{other['id']}", headers=owner.headers)).json()["entries"]
                  if x["ledger_id"] == bank)  # fmt: skip
    r = await client.patch(f"{A}/banking/entries/{oentry['id']}/reconcile", json={"bank_reconciliation_date": "2026-09-13"},
                           headers=owner.headers)  # fmt: skip
    assert r.status_code == 200 and r.json()["bank_reconciliation_date"] == "2026-09-13"
    bad = await client.patch(f"{A}/banking/entries/{oentry['id']}/reconcile", json={"bank_reconciliation_date": "2026-09-01"},
                             headers=owner.headers)  # fmt: skip
    assert bad.status_code == 400
    acct = next(
        x for x in (await client.get(f"{A}/banking/accounts", headers=owner.headers)).json() if x["ledger_id"] == bank
    )
    assert acct["unreconciled_count"] == 0 and acct["ifsc"] == "HDFC0001"

    cheques = (await client.get(f"{A}/banking/cheques", params={"bank_ledger_id": bank}, headers=owner.headers)).json()
    assert [(c["instrument_no"], c["status"]) for c in cheques] == [("000101", "CLEARED")]
    pdf = await client.get(f"{A}/banking/cheques/{cheques[0]['entry_id']}/print", headers=owner.headers)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


async def test_non_bank_ledger_rejected(client, owner):
    lg = await ledgers(client, owner)
    r = await client.get(
        f"{A}/banking/{lg['CASH']}/reconciliation", params={"as_of": "2026-09-30"}, headers=owner.headers
    )
    assert r.status_code == 400
    r = await client.post(f"{A}/banking/{lg['CASH']}/statements/import", files={"file": ("x.csv", b"junk", "text/csv")},
                          headers=owner.headers)  # fmt: skip
    assert r.status_code == 400
