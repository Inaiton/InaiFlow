"""Pure payroll calculations (calc.py) — worked examples against the seeded statutory configs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.payroll import calc
from app.seeds.tax_rules import EPF, ESIC, INCOME_TAX, PT_SLABS

D = Decimal
CFG = calc.StatutoryConfig(epf=EPF, esic=ESIC, pt_slabs=PT_SLABS, income_tax=INCOME_TAX)


def structure(**kw) -> calc.Structure:
    base = {"basic": "10000", "epf_applicable": True, "esic_applicable": True, "pt_applicable": True}
    base.update(kw)
    return calc.parse_structure(base)


def line(st: calc.Structure, *, month=date(2026, 4, 1), lop="0", ot="0", units="0", regime="NEW", state=None,
         basis="CALENDAR", remaining=None, **prior) -> calc.LineResult:  # fmt: skip
    att = calc.AttendanceInput(days_present=D("30"), lop_days=D(lop), overtime_hours=D(ot), production_units=D(units))
    rem = remaining if remaining is not None else calc.remaining_fy_months(month, date(2026, 4, 1))
    inp = calc.LineInput(structure=st, attendance=att, tax_regime=regime, month=month,
                         basis_days=calc.basis_days(basis, month), remaining_months=rem, pt_state_code=state,
                         prior=calc.PriorYtd(**{k: D(v) for k, v in prior.items()}))  # fmt: skip
    return calc.compute_line(inp, CFG)


# ----------------------------------------------------------------- basics
def test_monthly_gross_and_parse():
    st = structure(basic="20000", da="5000", hra="8000", special="3000", conveyance="1600",
                   other_allowances=[{"name": "Shift", "amount": "400"}])  # fmt: skip
    assert calc.monthly_gross(st) == D("38000.00")


def test_basis_days():
    assert calc.basis_days("CALENDAR", date(2026, 2, 1)) == 28
    assert calc.basis_days("CALENDAR", date(2028, 2, 1)) == 29
    assert calc.basis_days("FIXED_26", date(2026, 2, 1)) == 26
    assert calc.basis_days("FIXED_30", date(2026, 7, 1)) == 30
    with pytest.raises(ValueError):
        calc.basis_days("WEEKLY", date(2026, 2, 1))


def test_remaining_fy_months():
    assert calc.remaining_fy_months(date(2026, 4, 1), date(2026, 4, 1)) == 12
    assert calc.remaining_fy_months(date(2026, 9, 1), date(2026, 4, 1)) == 7
    assert calc.remaining_fy_months(date(2027, 3, 1), date(2026, 4, 1)) == 1


def test_lop_proration_calendar_basis():
    # 30-day month (April), 3 LOP days: factor 27/30
    r = line(structure(basic="30000", hra="12000", epf_applicable=False, esic_applicable=False, pt_applicable=False),
             lop="3")  # fmt: skip
    assert r.earnings["basic"] == D("27000.00")
    assert r.earnings["hra"] == D("10800.00")
    assert r.gross == D("37800.00")


def test_lop_proration_fixed_26_basis():
    r = line(structure(basic="26000", epf_applicable=False, esic_applicable=False, pt_applicable=False),
             lop="1", basis="FIXED_26")  # fmt: skip
    assert r.earnings["basic"] == D("25000.00")


def test_overtime_and_piece_rate():
    # hourly = (basic+da)/30/8 * 2 = (24000)/240*2 = 200 ; 5h -> 1000 ; piece 2.50 x 400 units = 1000
    st = structure(basic="20000", da="4000", piece_rate="2.50", epf_applicable=False, esic_applicable=False,
                   pt_applicable=False)  # fmt: skip
    r = line(st, ot="5", units="400")
    assert r.earnings["overtime"] == D("1000.00")
    assert r.earnings["piece_rate"] == D("1000.00")
    assert r.gross == D("26000.00")


# ----------------------------------------------------------------- EPF
def test_epf_capped_at_wage_ceiling():
    r = line(structure(basic="20000", da="5000", esic_applicable=False, pt_applicable=False))
    assert r.epf.epf_wages == D("15000")
    assert r.deductions["epf"] == D("1800")
    assert r.employer["eps"] == D("1250")  # 8.33% of 15000 = 1249.50 -> 1250, cap 1250
    assert r.employer["epf_er"] == D("550")  # remainder of 12%
    assert r.employer["edli"] == D("75")
    assert r.employer["epf_admin"] == D("75")


def test_epf_below_ceiling():
    r = line(structure(basic="9000", da="1000", esic_applicable=False, pt_applicable=False))
    assert r.epf.epf_wages == D("10000")
    assert r.deductions["epf"] == D("1200")
    assert r.employer["eps"] == D("833")  # 833.00
    assert r.employer["epf_er"] == D("367")
    assert r.employer["edli"] == D("50")
    assert r.employer["epf_admin"] == D("50")


def test_epf_not_applicable():
    r = line(structure(basic="9000", epf_applicable=False, esic_applicable=False, pt_applicable=False))
    assert "epf" not in r.deductions and "eps" not in r.employer
    assert r.epf.epf_wages == 0


def test_admin_minimum_tops_up_first_epf_line():
    a = line(structure(basic="10000", esic_applicable=False, pt_applicable=False))
    b = line(structure(basic="12000", esic_applicable=False, pt_applicable=False))
    calc.apply_admin_minimum([a, b], CFG.epf)
    assert a.employer["epf_admin"] + b.employer["epf_admin"] == D("500")
    assert b.employer["epf_admin"] == D("60")
    assert a.employer_total == sum(a.employer.values())


# ----------------------------------------------------------------- ESIC
def test_esic_at_threshold_21000_applies():
    r = line(structure(basic="21000", epf_applicable=False, pt_applicable=False))
    assert r.gross == D("21000.00")
    assert r.deductions["esic"] == D("158")  # 157.50 rounded UP
    assert r.employer["esic_er"] == D("682.50")


def test_esic_above_threshold_not_applicable():
    r = line(structure(basic="21000.01", epf_applicable=False, pt_applicable=False))
    assert "esic" not in r.deductions and "esic_er" not in r.employer
    assert not r.esic.applicable


# ----------------------------------------------------------------- PT
def test_pt_maharashtra_monthly_and_february():
    st = structure(basic="25000", epf_applicable=False, esic_applicable=False)
    assert line(st, state="27", month=date(2026, 5, 1)).deductions["pt"] == D("200")
    assert line(st, state="27", month=date(2027, 2, 1)).deductions["pt"] == D("300")
    low = structure(basic="9000", epf_applicable=False, esic_applicable=False)
    assert line(low, state="27").deductions["pt"] == D("175")
    assert "pt" not in line(structure(basic="7000", epf_applicable=False, esic_applicable=False),
                            state="27").deductions  # fmt: skip


def test_pt_karnataka_gap_boundary():
    assert line(structure(basic="15000", epf_applicable=False, esic_applicable=False),
                state="29").deductions["pt"] == D("200")  # fmt: skip
    assert "pt" not in line(structure(basic="14999.99", epf_applicable=False, esic_applicable=False),
                            state="29").deductions  # fmt: skip


def test_pt_tamil_nadu_half_yearly_as_monthly_equivalent():
    # 10000/month -> 60000 half-yearly -> slab 45000.01..60000 = 930 per half-year -> 155.00/month
    r = line(structure(basic="10000", epf_applicable=False, esic_applicable=False), state="33")
    assert r.deductions["pt"] == D("155.00")
    # 6000/month -> 36000 half-yearly -> 425 -> 70.83/month
    r = line(structure(basic="6000", epf_applicable=False, esic_applicable=False), state="33")
    assert r.deductions["pt"] == D("70.83")


def test_pt_unknown_state_or_not_applicable():
    assert "pt" not in line(structure(basic="50000", epf_applicable=False, esic_applicable=False)).deductions
    assert "pt" not in line(structure(basic="50000", epf_applicable=False, esic_applicable=False,
                                      pt_applicable=False), state="27").deductions  # fmt: skip


# ----------------------------------------------------------------- income tax
def test_annual_tax_new_regime_rebate_and_marginal_relief():
    new = INCOME_TAX["regimes"]["NEW"]
    assert calc.annual_tax(D("1125000"), new, D("4")) == D("0")  # full 87A rebate up to 12L
    # 12.10L: slab tax 61500 but marginal relief limits to 10000 (+4% cess)
    assert calc.annual_tax(D("1210000"), new, D("4")) == D("10400")
    # 17.25L: 20000 + 40000 + 60000 + 25000 = 145000 + cess 5800
    assert calc.annual_tax(D("1725000"), new, D("4")) == D("150800")


def test_annual_tax_old_regime():
    old = INCOME_TAX["regimes"]["OLD"]
    assert calc.annual_tax(D("500000"), old, D("4")) == D("0")  # 87A
    # 1728400: 12500 + 100000 + 218520 = 331020 ; cess 13240.80 -> 344261 (rupee)
    assert calc.annual_tax(D("1728400"), old, D("4")) == D("344261")


def test_tds_new_regime_projection():
    st = structure(basic="150000", epf_applicable=False, esic_applicable=False, pt_applicable=False)
    r = line(st, regime="NEW")
    # projected 18L - 75k = 17.25L -> 150800 / 12 = 12566.67 -> 12567
    assert r.deductions["tds"] == D("12567")


def test_tds_old_regime_projection_with_epf_80c():
    st = structure(basic="150000", esic_applicable=False, pt_applicable=False)
    r = line(st, regime="OLD")
    # 18L - 50k - EPF 1800*12 = 1728400 -> 344261 / 12 = 28688.42 -> 28688
    assert r.deductions["tds"] == D("28688")


def test_tds_uses_ytd_and_remaining_months():
    st = structure(basic="150000", epf_applicable=False, esic_applicable=False, pt_applicable=False)
    # September: 5 prior months gross 750000 paid, tds 50000 deducted; remaining 7 -> projected 18L
    r = line(st, month=date(2026, 9, 1), gross="750000", tds="50000")
    assert r.deductions["tds"] == D("14400")  # (150800 - 50000) / 7 = 14400


def test_tds_override_wins_and_never_negative():
    st = structure(basic="150000", monthly_tds_override="5000", epf_applicable=False, esic_applicable=False,
                   pt_applicable=False)  # fmt: skip
    assert line(st).deductions["tds"] == D("5000")
    st2 = structure(basic="150000", epf_applicable=False, esic_applicable=False, pt_applicable=False)
    assert "tds" not in line(st2, month=date(2026, 9, 1), gross="750000", tds="200000").deductions


# ----------------------------------------------------------------- totals
def test_net_pay_and_other_deductions():
    st = structure(basic="15000", hra="5000", other_deductions=[{"name": "Canteen", "amount": "300"}])
    r = line(st, state="29")
    # gross 20000; EPF 1800; ESIC ceil(150) = 150; PT 200; canteen 300
    assert r.gross == D("20000.00")
    assert r.deductions == {"epf": D("1800"), "esic": D("150"), "pt": D("200"), "Canteen": D("300.00")}
    assert r.total_deductions == D("2450.00")
    assert r.net_pay == D("17550.00")
    assert r.employer_total == D("1250") + D("550") + D("75") + D("75") + D("650.00")


def test_split_allocations_exact():
    parts = calc.split_by_share(D("10000.00"), [D("33.33"), D("33.33"), D("33.34")])
    assert parts == [D("3333.00"), D("3333.00"), D("3334.00")]
    parts = calc.split_by_share(D("100.00"), [D("33.3333"), D("66.6667")])
    assert sum(parts) == D("100.00")


def test_amount_in_words():
    assert calc.amount_in_words(D("17550.00")) == "Rupees Seventeen Thousand Five Hundred Fifty Only"
    assert calc.amount_in_words(D("1234567.50")) == (
        "Rupees Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven and Fifty Paise Only"
    )
    assert calc.amount_in_words(D("0")) == "Rupees Zero Only"
