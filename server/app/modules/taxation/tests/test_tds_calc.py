"""TDS/TCS computation (pure) from the TDS_SECTIONS config."""

from datetime import date
from decimal import Decimal

from app.modules.taxation.tds_calc import challan_due_date, compute_tds, deductee_class, fy_quarter
from app.seeds.tax_rules import TDS_SECTIONS

D = Decimal
SECTIONS = {s["section"]: s for s in TDS_SECTIONS["sections"]}


def test_194c_single_threshold_individual_rate():
    r = compute_tds(SECTIONS["194C"], amount=D("40000"), ytd=D("0"), pan="ABCPE1234F", deductee_type=None)
    assert r.applicable and r.rate == D("1") and r.tds_amount == D("400")


def test_194c_company_rate_from_pan_or_type():
    r = compute_tds(SECTIONS["194C"], amount=D("40000"), ytd=D("0"), pan="ABCCE1234F", deductee_type=None)
    assert r.rate == D("2")
    r = compute_tds(SECTIONS["194C"], amount=D("40000"), ytd=D("0"), pan="ABCPE1234F", deductee_type="COMPANY")
    assert r.rate == D("2")


def test_below_thresholds_not_applicable():
    r = compute_tds(SECTIONS["194C"], amount=D("20000"), ytd=D("50000"), pan="ABCPE1234F", deductee_type=None)
    assert not r.applicable and r.tds_amount == D("0")


def test_annual_threshold_crossed_taxes_the_aggregate():
    r = compute_tds(SECTIONS["194C"], amount=D("20000"), ytd=D("90000"), pan="ABCPE1234F", deductee_type=None)
    assert r.applicable
    assert r.tds_amount == D("1100")  # 1% of 110000


def test_after_threshold_only_current_amount():
    r = compute_tds(SECTIONS["194J(b)"], amount=D("10000"), ytd=D("40000"), pan="ABCPE1234F", deductee_type=None)
    assert r.tds_amount == D("1000")


def test_no_pan_20_percent():
    r = compute_tds(SECTIONS["194J(b)"], amount=D("50000"), ytd=D("0"), pan=None, deductee_type=None)
    assert r.rate == D("20") and r.tds_amount == D("10000") and not r.pan_available


def test_194q_on_excess_only():
    r = compute_tds(SECTIONS["194Q"], amount=D("1000000"), ytd=D("4500000"), pan="ABCCE1234F", deductee_type=None)
    assert r.tds_amount == D("500")  # 0.1% of 5,00,000 above 50L


def test_tcs_scrap_no_threshold():
    r = compute_tds(SECTIONS["206C(1)"], amount=D("1000"), ytd=D("0"), pan="ABCPE1234F", deductee_type=None)
    assert r.applicable and r.tds_amount == D("10")


def test_deductee_class():
    assert deductee_class("INDIVIDUAL", None) == "INDIVIDUAL"
    assert deductee_class(None, "ABCHE1234F") == "INDIVIDUAL"
    assert deductee_class(None, "ABCFE1234F") == "COMPANY"
    assert deductee_class(None, None) == "INDIVIDUAL"


def test_challan_due_dates():
    assert challan_due_date(date(2026, 9, 1), TDS_SECTIONS) == date(2026, 10, 7)
    assert challan_due_date(date(2026, 12, 1), TDS_SECTIONS) == date(2027, 1, 7)
    assert challan_due_date(date(2027, 3, 1), TDS_SECTIONS) == date(2027, 4, 30)


def test_fy_quarter():
    assert fy_quarter("2026-Q1") == (date(2026, 4, 1), date(2026, 6, 30))
    assert fy_quarter("2026-27-Q4") == (date(2027, 1, 1), date(2027, 3, 31))
