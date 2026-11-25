"""Financial-year and month helpers.

Folder naming convention (single, documented format): ``"{MM} - {Full month name} {YYYY}"``,
e.g. ``"09 - September 2026"``; FY label ``"FY 2026-27"`` (``"FY 2026"`` for calendar-year FYs).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip


@dataclass(frozen=True, slots=True)
class FinancialYear:
    label: str
    start: date
    end: date

    def contains(self, d: date) -> bool:
        return self.start <= d <= self.end


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 Feb
        return d.replace(year=d.year + years, day=28)


def fy_label(start: date, end: date) -> str:
    if start.year == end.year:
        return f"FY {start.year}"
    return f"FY {start.year}-{end.year % 100:02d}"


def fy_for_date(d: date, fy_begins_from: date) -> FinancialYear:
    """FY containing ``d`` for an org whose FY starts on ``fy_begins_from``'s month/day."""
    try:
        start = date(d.year, fy_begins_from.month, fy_begins_from.day)
    except ValueError:
        start = date(d.year, fy_begins_from.month, 28)
    if start > d:
        start = _add_years(start, -1)
    end = _add_years(start, 1) - timedelta(days=1)
    return FinancialYear(fy_label(start, end), start, end)


def month_start(d: date) -> date:
    return d.replace(day=1)


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def add_months(d: date, months: int) -> date:
    idx = d.year * 12 + (d.month - 1) + months
    year, month = divmod(idx, 12)
    day = min(d.day, calendar.monthrange(year, month + 1)[1])
    return date(year, month + 1, day)


def month_folder_name(d: date) -> str:
    return f"{d.month:02d} - {MONTH_NAMES[d.month - 1]} {d.year}"


def parse_month(value: str) -> date:
    """Parse ``YYYY-MM`` (query-string month) into the first day of that month."""
    try:
        year_s, month_s = value.split("-")
        result = date(int(year_s), int(month_s), 1)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"invalid month {value!r}, expected YYYY-MM") from exc
    if len(year_s) != 4:
        raise ValueError(f"invalid month {value!r}, expected YYYY-MM")
    return result


def format_month(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def months_in_fy(fy: FinancialYear) -> list[date]:
    out: list[date] = []
    cur = month_start(fy.start)
    while cur <= fy.end:
        out.append(cur)
        cur = add_months(cur, 1)
    return out
