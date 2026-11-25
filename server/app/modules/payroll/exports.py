"""Payroll file renderers (pure): payslip PDF, NEFT bulk CSV, EPF ECR 2.0, ESIC and PT CSVs."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.adapters.export import Letterhead, Report, get_exporter
from app.core.fy import MONTH_NAMES
from app.core.money import ZERO, D, round_rupee, to_str
from app.core.security import csv_safe
from app.modules.payroll.calc import amount_in_words

LABELS = {
    "basic": "Basic", "da": "Dearness Allowance", "hra": "House Rent Allowance", "special": "Special Allowance",
    "conveyance": "Conveyance", "overtime": "Overtime", "piece_rate": "Piece-rate Earnings",
    "epf": "EPF (Employee 12%)", "esic": "ESIC (Employee)", "pt": "Professional Tax", "tds": "Income Tax (TDS u/s 192)",
    "eps": "EPS (Employer)", "epf_er": "EPF (Employer)", "edli": "EDLI", "epf_admin": "EPF Admin Charges",
    "esic_er": "ESIC (Employer)",
}  # fmt: skip


@dataclass(frozen=True, slots=True)
class SlipLine:
    """Everything a payslip / statutory row needs (built by the service from a run line + employee)."""

    emp_code: str
    full_name: str
    designation: str | None
    department: str | None
    pan: str | None
    uan_epf: str | None
    esic_ip_no: str | None
    bank_account_no: str | None
    bank_ifsc: str | None
    days_in_month: int
    days_worked: Decimal
    lop_days: Decimal
    earnings: dict[str, Decimal]
    deductions: dict[str, Decimal]
    employer: dict[str, Decimal]
    gross: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    epf_wages: Decimal = ZERO
    eps_wages: Decimal = ZERO
    edli_wages: Decimal = ZERO


def month_label(month: date) -> str:
    return f"{MONTH_NAMES[month.month - 1]} {month.year}"


def label(key: str) -> str:
    return LABELS.get(key, key)


def _money(v: Decimal) -> str:
    return f"₹ {to_str(v)}"


def _mask(account: str | None) -> str:
    if not account:
        return "-"
    return "XXXX" + account[-4:] if len(account) > 4 else account


def render_payslip(org: Any, line: SlipLine, month: date) -> bytes:
    """``org`` is an ``organization.interface.OrgBrief``."""
    lines = [*org.address_lines]
    if org.gstin:
        lines.append(f"GSTIN: {org.gstin}")
    head = Letterhead(name=org.legal_name, lines=lines)
    earn = list(line.earnings.items())
    ded = list(line.deductions.items())
    rows = []
    for i in range(max(len(earn), len(ded))):
        e = earn[i] if i < len(earn) else None
        d = ded[i] if i < len(ded) else None
        rows.append([label(e[0]) if e else "", to_str(e[1]) if e else "", label(d[0]) if d else "",
                     to_str(d[1]) if d else ""])  # fmt: skip
    rows.append(["Gross Earnings", to_str(line.gross), "Total Deductions", to_str(line.total_deductions)])
    blocks: list[dict[str, Any]] = [
        {"type": "kv", "data": {"rows": [
            {"label": "Employee", "value": f"{line.full_name} ({line.emp_code})"},
            {"label": "Designation", "value": line.designation or "-"},
            {"label": "Department", "value": line.department or "-"},
            {"label": "PAN", "value": line.pan or "-"},
            {"label": "UAN", "value": line.uan_epf or "-"},
            {"label": "ESIC IP No.", "value": line.esic_ip_no or "-"},
            {"label": "Bank A/c", "value": f"{_mask(line.bank_account_no)} {line.bank_ifsc or ''}".strip()},
            {"label": "Days in month / paid / LOP",
             "value": f"{line.days_in_month} / {to_str(line.days_worked)} / {to_str(line.lop_days)}"},
        ]}},
        {"type": "table", "data": {"columns": ["Earnings", "Amount (₹)", "Deductions", "Amount (₹)"], "rows": rows}},
        {"type": "heading", "data": {"text": f"Net Pay: {_money(line.net_pay)}", "level": 2}},
        {"type": "paragraph", "data": {"text": amount_in_words(line.net_pay)}},
    ]  # fmt: skip
    if line.employer:
        blocks.append({"type": "table", "data": {
            "columns": ["Employer contributions (not part of net pay)", "Amount (₹)"],
            "rows": [[label(k), to_str(v)] for k, v in line.employer.items()]}})  # fmt: skip
    blocks.append({"type": "paragraph", "data": {"text": "This is a computer-generated payslip."}})
    report = Report(title=f"Payslip for {month_label(month)}", blocks=blocks, letterhead=head,
                    footer=f"{org.legal_name} · Payslip {line.emp_code} · {month_label(month)}")  # fmt: skip
    return get_exporter().render(report, "pdf")


# ----------------------------------------------------------------- CSV / text files
def _cell(value: Any) -> str:
    """Neutralise spreadsheet formula injection in free-text cells."""
    return str(csv_safe("" if value is None else str(value)))


def _csv(header: list[str], rows: list[list[Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(header)
    for r in rows:
        w.writerow([_cell(c) for c in r])
    return buf.getvalue()


def bank_file_csv(lines: list[SlipLine], month: date, org_name: str) -> str:
    narration = f"Salary {month_label(month)}"[:30]
    rows = [[ln.full_name, ln.bank_account_no, ln.bank_ifsc, to_str(ln.net_pay), narration]
            for ln in lines if ln.net_pay > 0]  # fmt: skip
    return _csv(["Beneficiary Name", "Beneficiary Account Number", "IFSC", "Amount", "Narration"], rows)


def _int(v: Decimal) -> str:
    return str(int(round_rupee(v)))


def epf_ecr(lines: list[SlipLine]) -> str:
    """ECR 2.0: ``UAN#~#Name#~#Gross#~#EPF#~#EPS#~#EDLI#~#EE#~#EPS share#~#ER share#~#NCP days#~#Refund``."""
    out = []
    for ln in lines:
        if not ln.epf_wages:
            continue
        fields = [ln.uan_epf or "", ln.full_name.replace("#~#", " "), _int(ln.gross), _int(ln.epf_wages),
                  _int(ln.eps_wages), _int(ln.edli_wages), _int(ln.deductions.get("epf", ZERO)),
                  _int(ln.employer.get("eps", ZERO)), _int(ln.employer.get("epf_er", ZERO)),
                  str(int(round_rupee(ln.lop_days))), "0"]  # fmt: skip
        out.append("#~#".join(fields))
    return "\n".join(out) + ("\n" if out else "")


def esic_csv(lines: list[SlipLine]) -> str:
    rows = [[ln.esic_ip_no, ln.full_name, to_str(ln.days_worked), to_str(ln.gross)]
            for ln in lines if ln.deductions.get("esic") or ln.employer.get("esic_er")]  # fmt: skip
    return _csv(["IP Number", "IP Name", "No of Days for which wages paid", "Total Monthly Wages"], rows)


def pt_csv(lines: list[SlipLine], state_code: str | None) -> str:
    rows = [[ln.emp_code, ln.full_name, state_code or "", to_str(ln.gross), to_str(ln.deductions["pt"])]
            for ln in lines if ln.deductions.get("pt")]  # fmt: skip
    total = sum((D(r[4]) for r in rows), ZERO)
    rows.append(["TOTAL", "", "", "", to_str(total)])
    return _csv(["Emp Code", "Employee Name", "State", "Gross Salary", "Professional Tax"], rows)
