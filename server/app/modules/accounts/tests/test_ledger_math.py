"""Outstanding bills / ageing (pure) and amount in words."""

from datetime import date
from decimal import Decimal

from app.modules.accounts.ledger_math import BillEntry, bucket_edges, bucket_for, bucket_labels, outstanding_bills
from app.modules.accounts.words import amount_in_words

D = Decimal
OPEN = date(2026, 4, 1)


def e(day, kind, amount, allocs=None, no="SI/1"):
    return BillEntry(date(2026, 4, day), no, kind, D(amount), allocs or [])


def test_new_ref_and_against_ref():
    bills = outstanding_bills(
        natural_side="DR", opening=D("0"), opening_date=OPEN, credit_days=30,
        entries=[
            e(1, "DR", "1000", [{"ref_type": "NEW_REF", "ref_name": "INV1", "amount": "1000"}]),
            e(2, "DR", "500", [{"ref_type": "NEW_REF", "ref_name": "INV2", "amount": "500"}]),
            e(5, "CR", "400", [{"ref_type": "AGAINST_REF", "ref_name": "INV2", "amount": "400"}]),
        ],
    )  # fmt: skip
    by = {b.ref_name: b for b in bills}
    assert by["INV1"].pending == D("1000") and by["INV1"].due_date == date(2026, 5, 1)
    assert by["INV2"].pending == D("100")


def test_unallocated_entries_fifo():
    bills = outstanding_bills(
        natural_side="DR", opening=D("200"), opening_date=OPEN, credit_days=None,
        entries=[e(2, "DR", "1000", no="SI/1"), e(3, "DR", "300", no="SI/2"), e(4, "CR", "700")],
    )  # fmt: skip
    by = {b.ref_name: b.pending for b in bills}
    # receipt 700 settles opening 200 first, then 500 of SI/1
    assert by == {"SI/1": D("500"), "SI/2": D("300")}


def test_advance_left_on_account():
    bills = outstanding_bills(natural_side="CR", opening=D("0"), opening_date=OPEN, credit_days=None,
                              entries=[e(2, "DR", "50", no="PV/1")])  # fmt: skip
    assert [(b.ref_name, b.pending) for b in bills] == [("On Account", D("50"))]


def test_buckets():
    edges = bucket_edges("30,60,90")
    assert bucket_labels(edges) == ["0-30", "31-60", "61-90", ">90"]
    assert [bucket_for(d, edges) for d in (0, 30, 31, 90, 91)] == [0, 0, 1, 2, 3]


def test_amount_in_words_indian():
    assert amount_in_words(D("1250000.50")) == "Rupees Twelve Lakh Fifty Thousand and Fifty Paise Only"
    assert amount_in_words(D("101")) == "Rupees One Hundred One Only"
    assert amount_in_words(D("0")) == "Rupees Zero Only"
    assert amount_in_words(D("23456789")) == (
        "Rupees Two Crore Thirty Four Lakh Fifty Six Thousand Seven Hundred Eighty Nine Only"
    )
