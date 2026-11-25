"""Pure payroll calculations (no I/O). Statutory numbers come from the ``PAYROLL_STATUTORY`` configs.

Conventions (see docs/plan/decisions/S3.md):
* every amount is ``Decimal``; earnings/ESIC employer/PT are quantized to 2 dp; EPF/EPS/EDLI/admin follow
  EPFO rupee rounding; the ESIC employee share rounds UP to the rupee; TDS rounds to the rupee.
* breakdown keys — earnings: basic da hra special conveyance <other allowance names> overtime piece_rate;
  deductions: epf esic pt tds <other deduction names>; employer: eps epf_er edli epf_admin esic_er.
  Zero amounts are omitted from the breakdowns.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.money import ZERO, D, ceil_rupee, q2, round_rupee

HUNDRED = Decimal(100)
OVERTIME_MULTIPLIER = Decimal(2)  # Factories Act s.59: twice the ordinary rate
DEFAULT_80C_CAP = Decimal("150000")  # used only when the INCOME_TAX config carries no ``section_80c_cap``
FIXED_COMPONENTS = ("basic", "da", "hra", "special", "conveyance")
EMPLOYER_KEYS = ("eps", "epf_er", "edli", "epf_admin", "esic_er")
STATUTORY_DEDUCTIONS = ("epf", "esic", "pt", "tds")
BASIS = {"CALENDAR": None, "FIXED_26": 26, "FIXED_30": 30}


# ----------------------------------------------------------------- inputs
@dataclass(frozen=True, slots=True)
class Structure:
    basic: Decimal
    da: Decimal = ZERO
    hra: Decimal = ZERO
    special: Decimal = ZERO
    conveyance: Decimal = ZERO
    other_allowances: tuple[tuple[str, Decimal], ...] = ()
    other_deductions: tuple[tuple[str, Decimal], ...] = ()
    epf_applicable: bool = True
    esic_applicable: bool = True
    pt_applicable: bool = True
    piece_rate: Decimal | None = None
    monthly_tds_override: Decimal | None = None


def _opt(value: Any) -> Decimal | None:
    return None if value is None or value == "" else D(value)


def parse_structure(data: dict[str, Any]) -> Structure:
    """Build a ``Structure`` from the stored ``salary_structure`` JSON (decimal strings)."""

    def comps(key: str) -> tuple[tuple[str, Decimal], ...]:
        return tuple((str(c["name"]), D(c["amount"])) for c in data.get(key) or [])

    return Structure(
        basic=D(data.get("basic") or 0),
        da=D(data.get("da") or 0),
        hra=D(data.get("hra") or 0),
        special=D(data.get("special") or 0),
        conveyance=D(data.get("conveyance") or 0),
        other_allowances=comps("other_allowances"),
        other_deductions=comps("other_deductions"),
        epf_applicable=bool(data.get("epf_applicable", True)),
        esic_applicable=bool(data.get("esic_applicable", True)),
        pt_applicable=bool(data.get("pt_applicable", True)),
        piece_rate=_opt(data.get("piece_rate")),
        monthly_tds_override=_opt(data.get("monthly_tds_override")),
    )


@dataclass(frozen=True, slots=True)
class AttendanceInput:
    days_present: Decimal
    lop_days: Decimal = ZERO
    overtime_hours: Decimal = ZERO
    production_units: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class PriorYtd:
    """Sums over earlier LOCKED/PAID payroll runs of the same FY (for the s.192 projection)."""

    gross: Decimal = ZERO
    tds: Decimal = ZERO
    epf: Decimal = ZERO
    pt: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class StatutoryConfig:
    epf: dict[str, Any]
    esic: dict[str, Any]
    pt_slabs: dict[str, Any]
    income_tax: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LineInput:
    structure: Structure
    attendance: AttendanceInput
    tax_regime: str
    month: date
    basis_days: int
    remaining_months: int
    pt_state_code: str | None = None
    prior: PriorYtd = field(default_factory=PriorYtd)


# ----------------------------------------------------------------- outputs
@dataclass(slots=True)
class EpfResult:
    epf_wages: Decimal = ZERO
    eps_wages: Decimal = ZERO
    edli_wages: Decimal = ZERO
    employee: Decimal = ZERO
    eps: Decimal = ZERO
    employer_epf: Decimal = ZERO
    edli: Decimal = ZERO
    admin: Decimal = ZERO


@dataclass(slots=True)
class EsicResult:
    applicable: bool = False
    wages: Decimal = ZERO
    employee: Decimal = ZERO
    employer: Decimal = ZERO


@dataclass(slots=True)
class LineResult:
    earnings: dict[str, Decimal]
    deductions: dict[str, Decimal]
    employer: dict[str, Decimal]
    epf: EpfResult
    esic: EsicResult

    @property
    def gross(self) -> Decimal:
        return q2(sum(self.earnings.values(), ZERO))

    @property
    def total_deductions(self) -> Decimal:
        return q2(sum(self.deductions.values(), ZERO))

    @property
    def net_pay(self) -> Decimal:
        return q2(self.gross - self.total_deductions)

    @property
    def employer_total(self) -> Decimal:
        return q2(sum(self.employer.values(), ZERO))

    @property
    def other_deductions_total(self) -> Decimal:
        return q2(sum((v for k, v in self.deductions.items() if k not in STATUTORY_DEDUCTIONS), ZERO))


# ----------------------------------------------------------------- helpers
def days_in_month(month: date) -> int:
    return calendar.monthrange(month.year, month.month)[1]


def basis_days(basis: str, month: date) -> int:
    """Working-days basis for proration: CALENDAR (days in month) | FIXED_26 | FIXED_30."""
    if basis not in BASIS:
        raise ValueError(f"unknown working_days_basis {basis!r}")
    return BASIS[basis] or days_in_month(month)


def remaining_fy_months(month: date, fy_start: date) -> int:
    """Months left in the FY including ``month`` (April with an April FY -> 12, March -> 1)."""
    elapsed = (month.year - fy_start.year) * 12 + (month.month - fy_start.month)
    return max(12 - elapsed, 1)


def monthly_gross(st: Structure) -> Decimal:
    """Full-month fixed gross (no LOP, overtime or piece-rate)."""
    fixed = st.basic + st.da + st.hra + st.special + st.conveyance
    return q2(fixed + sum((a for _, a in st.other_allowances), ZERO))


def _put(target: dict[str, Decimal], key: str, value: Decimal) -> None:
    if value:
        target[key] = target.get(key, ZERO) + value


def compute_earnings(st: Structure, att: AttendanceInput, basis: int) -> dict[str, Decimal]:
    days = D(basis)
    factor = max(days - att.lop_days, ZERO) / days
    out: dict[str, Decimal] = {}
    for name in FIXED_COMPONENTS:
        _put(out, name, q2(getattr(st, name) * factor))
    for name, amount in st.other_allowances:
        _put(out, name, q2(amount * factor))
    if att.overtime_hours:
        hourly = (st.basic + st.da) / days / Decimal(8) * OVERTIME_MULTIPLIER
        _put(out, "overtime", q2(hourly * att.overtime_hours))
    if st.piece_rate and att.production_units:
        _put(out, "piece_rate", q2(st.piece_rate * att.production_units))
    return out


def _rate(cfg: dict[str, Any], key: str) -> Decimal:
    return D(cfg[key]) / HUNDRED


def compute_epf(earnings: dict[str, Decimal], cfg: dict[str, Any]) -> EpfResult:
    wages = sum((earnings.get(c, ZERO) for c in cfg.get("wage_components", ["basic", "da"])), ZERO)
    ceiling = D(cfg["wage_ceiling"])
    epf_wages = min(wages, ceiling)
    employee = round_rupee(epf_wages * _rate(cfg, "employee_rate"))
    eps = min(round_rupee(epf_wages * _rate(cfg, "employer_eps_rate")), D(cfg["employer_eps_cap"]))
    edli = round_rupee(epf_wages * _rate(cfg, "edli_rate"))
    if cfg.get("edli_cap") is not None:
        edli = min(edli, D(cfg["edli_cap"]))
    return EpfResult(
        epf_wages=epf_wages, eps_wages=epf_wages, edli_wages=epf_wages, employee=employee, eps=eps,
        employer_epf=employee - eps, edli=edli, admin=round_rupee(epf_wages * _rate(cfg, "admin_charges_rate")),
    )  # fmt: skip


def compute_esic(gross: Decimal, cfg: dict[str, Any]) -> EsicResult:
    if gross > D(cfg["gross_ceiling"]) or gross <= 0:
        return EsicResult()
    employee = gross * _rate(cfg, "employee_rate")
    employee = ceil_rupee(employee) if cfg.get("employee_rounding", "CEIL_RUPEE") == "CEIL_RUPEE" else q2(employee)
    return EsicResult(True, gross, employee, q2(gross * _rate(cfg, "employer_rate")))


def _slab_amount(slabs: list[dict[str, Any]], income: Decimal, month: date) -> Decimal:
    chosen = None
    for slab in sorted(slabs, key=lambda s: D(s["min"])):
        if income >= D(slab["min"]):
            chosen = slab
    if chosen is None:
        return ZERO
    if month.month == 2 and chosen.get("feb_amount") is not None:
        return D(chosen["feb_amount"])
    return D(chosen["amount"])


def professional_tax(gross: Decimal, state_cfg: dict[str, Any] | None, month: date) -> Decimal:
    """MONTHLY states: slab on monthly gross (``feb_amount`` overrides February).

    HALF_YEARLY states (TN, Kerala) are handled as a monthly equivalent: the slab is looked up on
    ``gross x 6`` and one sixth of the half-yearly amount is deducted every month (2 dp)."""
    if not state_cfg:
        return ZERO
    slabs = state_cfg.get("slabs") or []
    if state_cfg.get("frequency") == "HALF_YEARLY":
        return q2(_slab_amount(slabs, gross * 6, month.replace(month=1)) / 6)
    return q2(_slab_amount(slabs, gross, month))


def _slab_tax(taxable: Decimal, slabs: list[dict[str, Any]]) -> Decimal:
    tax = ZERO
    for s in slabs:
        lo = D(s["from"])
        hi = D(s["to"]) if s.get("to") is not None else None
        if taxable <= lo:
            continue
        band = (min(taxable, hi) if hi is not None else taxable) - lo
        tax += band * D(s["rate"]) / HUNDRED
    return tax


def annual_tax(taxable: Decimal, regime: dict[str, Any], cess_rate: Decimal) -> Decimal:
    """Slab tax - 87A rebate (with marginal relief where configured) + surcharge + cess, rounded to the rupee."""
    taxable = max(taxable, ZERO)
    tax = _slab_tax(taxable, regime["slabs"])
    rebate = regime.get("rebate_87a")
    if rebate:
        limit = D(rebate["income_limit"])
        if taxable <= limit:
            tax = max(tax - D(rebate["max_rebate"]), ZERO)
        elif rebate.get("marginal_relief"):
            tax = min(tax, taxable - limit)
    surcharge_rate = ZERO
    for s in regime.get("surcharge") or []:
        if taxable > D(s["above"]):
            surcharge_rate = max(surcharge_rate, D(s["rate"]))
    tax += tax * surcharge_rate / HUNDRED
    tax += tax * cess_rate / HUNDRED
    return tax.quantize(Decimal(1), rounding=ROUND_HALF_UP)


def monthly_tds(inp: LineInput, gross: Decimal, epf_employee: Decimal, pt: Decimal, cfg: dict[str, Any]) -> Decimal:
    """Section 192: tax on projected annual taxable income less YTD TDS, spread over the remaining months."""
    if inp.structure.monthly_tds_override is not None:
        return q2(inp.structure.monthly_tds_override)
    regime = cfg["regimes"].get(inp.tax_regime) or cfg["regimes"]["NEW"]
    months = D(inp.remaining_months)
    taxable = inp.prior.gross + gross * months - D(regime.get("standard_deduction") or 0)
    if inp.tax_regime == "OLD":
        cap = D(cfg.get("section_80c_cap") or regime.get("section_80c_cap") or DEFAULT_80C_CAP)
        taxable -= min(inp.prior.epf + epf_employee * months, cap)
        taxable -= inp.prior.pt + pt * months  # s.16(iii) professional tax
    tax = annual_tax(taxable, regime, D(cfg.get("cess_rate") or 0))
    return round_rupee(max(tax - inp.prior.tds, ZERO) / months)


def compute_line(inp: LineInput, cfg: StatutoryConfig) -> LineResult:
    st = inp.structure
    earnings = compute_earnings(st, inp.attendance, inp.basis_days)
    gross = q2(sum(earnings.values(), ZERO))
    deductions: dict[str, Decimal] = {}
    employer: dict[str, Decimal] = {}

    epf = compute_epf(earnings, cfg.epf) if st.epf_applicable else EpfResult()
    _put(deductions, "epf", epf.employee)
    for key, value in (("eps", epf.eps), ("epf_er", epf.employer_epf), ("edli", epf.edli), ("epf_admin", epf.admin)):
        _put(employer, key, value)

    esic = compute_esic(gross, cfg.esic) if st.esic_applicable else EsicResult()
    _put(deductions, "esic", esic.employee)
    _put(employer, "esic_er", esic.employer)

    state_cfg = (cfg.pt_slabs.get("states") or {}).get(inp.pt_state_code or "") if st.pt_applicable else None
    pt = professional_tax(gross, state_cfg, inp.month)
    _put(deductions, "pt", pt)

    _put(deductions, "tds", monthly_tds(inp, gross, epf.employee, pt, cfg.income_tax))
    for name, amount in st.other_deductions:
        _put(deductions, name, q2(amount))
    return LineResult(earnings, deductions, employer, epf, esic)


def apply_admin_minimum(lines: list[LineResult], epf_cfg: dict[str, Any]) -> None:
    """EPF admin charges have a per-establishment monthly minimum: top up the first EPF line (in place)."""
    minimum = D(epf_cfg.get("admin_charges_min") or 0)
    members = [ln for ln in lines if ln.epf.epf_wages > 0]
    if not members or not minimum:
        return
    total = sum((ln.employer.get("epf_admin", ZERO) for ln in members), ZERO)
    if total < minimum:
        first = members[0]
        first.epf.admin += minimum - total
        first.employer["epf_admin"] = first.employer.get("epf_admin", ZERO) + (minimum - total)


def split_by_share(amount: Decimal, shares: list[Decimal]) -> list[Decimal]:
    """Split ``amount`` by percentage shares (2 dp); the last part takes the remainder so parts sum exactly."""
    if not shares:
        return []
    parts = [q2(amount * s / HUNDRED) for s in shares[:-1]]
    parts.append(q2(amount * sum(shares, ZERO) / HUNDRED) - sum(parts, ZERO))
    return parts


# ----------------------------------------------------------------- amount in words (Indian numbering)
_ONES = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]  # fmt: skip
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_hundred(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else "")


def _below_thousand(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(f"{_ONES[n // 100]} Hundred")
        n %= 100
    if n:
        parts.append(_below_hundred(n))
    return " ".join(parts)


def _words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    for unit, size in (("Crore", 10_000_000), ("Lakh", 100_000), ("Thousand", 1000)):
        if n >= size:
            parts.append(f"{_words(n // size) if unit == 'Crore' else _below_hundred(n // size)} {unit}")
            n %= size
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def amount_in_words(amount: Decimal) -> str:
    value = q2(amount)
    rupees = int(value)
    paise = int((value - rupees) * 100)
    text = f"Rupees {_words(rupees)}"
    if paise:
        text += f" and {_below_hundred(paise)} Paise"
    return text + " Only"
