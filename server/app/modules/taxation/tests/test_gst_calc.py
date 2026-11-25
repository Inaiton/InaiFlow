"""GST computation (pure): place-of-supply split, slabs, cess, round-off, GSTIN checksum."""

from decimal import Decimal

from app.modules.taxation.gst_calc import (
    GstContext,
    GstLine,
    compute_gst,
    gstin_checksum_char,
    hsn_for_return,
    is_valid_gstin,
    place_of_supply,
)

D = Decimal
SLABS = ["0", "0.25", "3", "5", "12", "18", "28"]


def ctx(**kw):
    base = {"org_state": "33", "pos_state": "33", "slabs": SLABS}
    base.update(kw)
    return GstContext(**base)


def test_intra_state_splits_cgst_sgst():
    r = compute_gst(ctx(), [GstLine(taxable=D("1000"), rate=D("18"), hsn="7208")])
    assert r.tax_split == "INTRA"
    assert (r.cgst, r.sgst, r.igst) == (D("90.00"), D("90.00"), D("0"))
    assert r.invoice_total == D("1180")
    assert r.round_off == D("0")


def test_inter_state_is_igst():
    r = compute_gst(ctx(pos_state="29"), [GstLine(taxable=D("1000"), rate=D("18"))])
    assert r.tax_split == "INTER"
    assert (r.cgst, r.sgst, r.igst) == (D("0"), D("0"), D("180.00"))


def test_sez_and_export_are_igst_even_within_state():
    assert compute_gst(ctx(is_sez=True), [GstLine(D("100"), D("5"))]).tax_split == "INTER"
    assert compute_gst(ctx(is_export=True), [GstLine(D("100"), D("5"))]).igst == D("5.00")


def test_round_off_to_nearest_rupee():
    r = compute_gst(ctx(), [GstLine(taxable=D("1001.30"), rate=D("18"))])
    # 1001.30 + 90.12 + 90.12 = 1181.54 -> 1182
    assert r.invoice_total == D("1182")
    assert r.round_off == D("0.46")


def test_negative_round_off():
    r = compute_gst(ctx(), [GstLine(taxable=D("1000.40"), rate=D("0"))])
    assert r.invoice_total == D("1000")
    assert r.round_off == D("-0.40")


def test_breakup_groups_by_hsn_and_rate():
    r = compute_gst(
        ctx(),
        [GstLine(D("100"), D("18"), "7208"), GstLine(D("200"), D("18"), "7208"), GstLine(D("50"), D("5"), "1001")],
    )
    rows = {(b.hsn, b.rate): b for b in r.breakup}
    assert rows[("7208", D("18"))].taxable == D("300")
    assert rows[("7208", D("18"))].cgst == D("27.00")
    assert rows[("1001", D("5"))].sgst == D("1.25")


def test_rate_not_in_slab_warns():
    r = compute_gst(ctx(), [GstLine(D("100"), D("17"))])
    assert any("17" in w for w in r.warnings)


def test_cess_ad_valorem_and_specific():
    r = compute_gst(
        ctx(),
        [GstLine(D("1000"), D("28"), cess_rate=D("12")), GstLine(D("100"), D("28"), qty=D("10"), cess_per_unit=D("4"))],
    )
    assert r.cess == D("160.00")


def test_reverse_charge_tax_not_in_invoice_total():
    r = compute_gst(ctx(reverse_charge=True), [GstLine(D("1000"), D("5"))])
    assert r.cgst == D("25.00")
    assert r.invoice_total == D("1000")


def test_place_of_supply_precedence():
    assert place_of_supply(override="29", party_state="27", party_gstin="24AAAAA0000A1Z5", org_state="33") == "29"
    assert place_of_supply(override=None, party_state="27", party_gstin="24AAAAA0000A1Z5", org_state="33") == "27"
    assert place_of_supply(override=None, party_state=None, party_gstin="24AAAAA0000A1Z5", org_state="33") == "24"
    assert place_of_supply(override=None, party_state=None, party_gstin=None, org_state="33") == "33"


def test_gstin_checksum():
    base = "27AAPFU0939F1Z"
    full = base + gstin_checksum_char(base)
    assert full == "27AAPFU0939F1ZV"
    assert is_valid_gstin(full)
    assert not is_valid_gstin("27AAPFU0939F1ZA")
    assert not is_valid_gstin("BAD")


def test_hsn_digit_rule():
    assert hsn_for_return("72085110", above_5cr=False) == "7208"
    assert hsn_for_return("72085110", above_5cr=True) == "720851"
    assert hsn_for_return(None, above_5cr=True) is None
