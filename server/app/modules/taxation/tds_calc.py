"""TDS / TCS computation — pure functions over one ``TDS_SECTIONS`` section entry (07_RULES §3).

Rules:
* rate: no PAN -> ``rate_no_pan`` (Sec 206AA/206CC); individual/HUF -> ``rate_individual``; else ``rate_company``.
  Deductee class comes from ``party_details.deductee_type`` or, if missing, the PAN's 4th character (P/H).
* thresholds: applicable when the single payment exceeds ``threshold_single`` or the FY aggregate (``ytd`` +
  amount) exceeds ``threshold_annual``; sections without thresholds always apply. When the annual threshold
  is crossed by this payment, tax is due on the whole aggregate (earlier payments were not taxed).
* ``applies_on_excess`` sections (194Q, 206C(1H)): tax only on the part of the aggregate above the threshold.
* amounts are rounded to the nearest rupee (Sec 288B).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.money import ZERO, round_rupee

INDIVIDUAL_TYPES = frozenset({"INDIVIDUAL", "HUF"})
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")


@dataclass(frozen=True, slots=True)
class TdsResult:
    applicable: bool
    section: str
    rate: Decimal
    tds_amount: Decimal
    base_amount: Decimal
    threshold_info: str
    pan_available: bool


def _dec(value: Any) -> Decimal | None:
    return None if value in (None, "") else Decimal(str(value))


def valid_pan(pan: str | None) -> bool:
    return bool(pan) and bool(PAN_RE.match(pan.strip().upper()))


def deductee_class(deductee_type: str | None, pan: str | None) -> str:
    if deductee_type:
        return "INDIVIDUAL" if deductee_type.upper() in INDIVIDUAL_TYPES else "COMPANY"
    if valid_pan(pan):
        return "INDIVIDUAL" if pan.strip().upper()[3] in ("P", "H") else "COMPANY"
    return "INDIVIDUAL"


def compute_tds(
    section: dict[str, Any], *, amount: Decimal, ytd: Decimal, pan: str | None, deductee_type: str | None
) -> TdsResult:
    has_pan = valid_pan(pan)
    if not has_pan:
        rate = Decimal(str(section["rate_no_pan"]))
    elif deductee_class(deductee_type, pan) == "INDIVIDUAL":
        rate = Decimal(str(section["rate_individual"]))
    else:
        rate = Decimal(str(section["rate_company"]))
    single, annual = _dec(section.get("threshold_single")), _dec(section.get("threshold_annual"))
    aggregate = ytd + amount
    info_parts = []
    if single is not None:
        info_parts.append(f"single > {single}")
    if annual is not None:
        info_parts.append(f"annual > {annual} (FY aggregate {aggregate})")
    info = "; ".join(info_parts) or "no threshold"

    if section.get("applies_on_excess") and annual is not None:
        base = max(aggregate - annual, ZERO) - max(ytd - annual, ZERO)
        applicable = base > 0
    elif single is None and annual is None:
        base, applicable = amount, True
    else:
        over_single = single is not None and amount > single
        over_annual = annual is not None and aggregate > annual
        applicable = over_single or over_annual
        crossed_now = annual is not None and over_annual and ytd <= annual and not over_single
        base = aggregate if crossed_now else amount
    tds = round_rupee(base * rate / Decimal(100)) if applicable else ZERO
    return TdsResult(applicable, section["section"], rate, tds, base if applicable else ZERO, info, has_pan)


def challan_due_date(month: date, config: dict[str, Any]) -> date:
    """ITNS 281: 7th of the following month; tax deducted in March is due on 30 April."""
    if month.month == 3:
        mm, dd = (int(x) for x in str(config.get("march_due_date", "04-30")).split("-"))
        return date(month.year, mm, dd)
    day = int(config.get("due_day_of_next_month", 7))
    year, mon = (month.year + 1, 1) if month.month == 12 else (month.year, month.month + 1)
    return date(year, mon, day)


_QUARTER_RE = re.compile(r"^(\d{4})(?:-\d{2})?-Q([1-4])$")
_Q_MONTHS = {1: (4, 6), 2: (7, 9), 3: (10, 12), 4: (1, 3)}


def fy_quarter(value: str) -> tuple[date, date]:
    """``2026-Q1`` / ``2026-27-Q1`` -> FY 2026-27 quarter 1 (Apr-Jun). Q4 = Jan-Mar of the next year."""
    m = _QUARTER_RE.match(value.strip().upper())
    if not m:
        raise ValueError("quarter must look like 2026-Q1 or 2026-27-Q1")
    fy, q = int(m.group(1)), int(m.group(2))
    start_m, end_m = _Q_MONTHS[q]
    year = fy + 1 if q == 4 else fy
    end_day = {3: 31, 6: 30, 9: 30, 12: 31}[end_m]
    return date(year, start_m, 1), date(year, end_m, end_day)
