from datetime import date

import pytest

from app.core.fy import fy_for_date, fy_label, month_folder_name, month_start, months_in_fy, parse_month


def test_april_fy_mid_year():
    fy = fy_for_date(date(2026, 9, 15), date(2026, 4, 1))
    assert fy.label == "FY 2026-27"
    assert fy.start == date(2026, 4, 1)
    assert fy.end == date(2027, 3, 31)


def test_april_fy_before_start_month_belongs_to_previous_fy():
    fy = fy_for_date(date(2027, 2, 10), date(2026, 4, 1))
    assert fy.label == "FY 2026-27"
    fy = fy_for_date(date(2026, 3, 31), date(2026, 4, 1))
    assert fy.label == "FY 2025-26"
    assert fy.start == date(2025, 4, 1)


def test_fy_begins_year_is_irrelevant_only_month_day_matter():
    assert fy_for_date(date(2030, 5, 1), date(2020, 4, 1)).label == "FY 2030-31"


def test_calendar_year_fy():
    fy = fy_for_date(date(2026, 6, 1), date(2026, 1, 1))
    assert fy.label == "FY 2026"
    assert fy.end == date(2026, 12, 31)


def test_century_rollover_label():
    assert fy_label(date(2099, 4, 1), date(2100, 3, 31)) == "FY 2099-00"


def test_month_folder_name_full_month():
    assert month_folder_name(date(2026, 9, 1)) == "09 - September 2026"
    assert month_folder_name(date(2026, 4, 17)) == "04 - April 2026"


def test_month_helpers():
    assert month_start(date(2026, 9, 30)) == date(2026, 9, 1)
    assert parse_month("2026-09") == date(2026, 9, 1)
    with pytest.raises(ValueError):
        parse_month("2026-13")
    months = months_in_fy(fy_for_date(date(2026, 9, 1), date(2026, 4, 1)))
    assert len(months) == 12 and months[0] == date(2026, 4, 1) and months[-1] == date(2027, 3, 1)
