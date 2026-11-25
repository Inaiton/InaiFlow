"""Bank statement parsers — pure functions (CSV, OFX 1.x SGML / 2.x XML, SWIFT MT940).

Statement sign convention (bank's view): ``debit`` = withdrawal (our bank ledger CR), ``credit`` = deposit
(our bank ledger DR). CSV columns are matched case/punctuation-insensitively against common Indian bank
headers; callers may pass ``columns={"date": [...], "debit": [...], ...}`` to extend the aliases
(``accounts_settings.bank_csv_columns``).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.core.money import ZERO


class StatementParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedLine:
    txn_date: date
    value_date: date | None
    description: str
    reference: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal | None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


DEFAULT_COLUMNS: dict[str, list[str]] = {
    "date": ["date", "txn date", "transaction date", "tran date", "posting date", "post date", "booking date",
             "trans date"],
    "value_date": ["value dt", "value date", "valuedate"],
    "description": ["narration", "description", "particulars", "remarks", "details", "transaction details",
                    "transaction remarks", "transaction description"],
    "reference": ["chq./ref.no.", "chq/ref no", "chq no", "cheque no", "cheque number", "chq/ref number",
                  "ref no", "ref no./cheque no.", "reference", "reference no", "utr", "instrument no"],
    "debit": ["withdrawal amt.", "withdrawal", "withdrawals", "withdrawal amount", "debit", "debit amount",
              "debit amt", "dr amount", "dr"],
    "credit": ["deposit amt.", "deposit", "deposits", "deposit amount", "credit", "credit amount", "credit amt",
               "cr amount", "cr"],
    "amount": ["amount", "transaction amount", "txn amount", "amount (inr)", "amount(inr)"],
    "type": ["dr/cr", "cr/dr", "type", "dr / cr", "debit/credit", "transaction type"],
    "balance": ["closing balance", "balance", "running balance", "available balance", "balance (inr)"],
}  # fmt: skip

DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y", "%d %b %Y",
                "%d %b %y", "%d.%m.%Y", "%d.%m.%y", "%Y/%m/%d", "%d/%b/%Y", "%d %B %Y", "%Y%m%d")  # fmt: skip


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    candidates = [text]
    if " " in text or "T" in text:
        candidates += [text.split("T")[0], text.split(" ")[0]]
    for cand in candidates:
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(cand, fmt).date()
            except ValueError:
                continue
    return None


def parse_amount(value: str | None, *, comma_decimal: bool = False) -> Decimal | None:
    if value is None:
        return None
    text = value.strip().replace("₹", "").replace("INR", "").replace(" ", "")
    suffix = None
    m = re.match(r"^(.*?)(cr|dr)\.?$", text, re.IGNORECASE)
    if m and m.group(1):
        text, suffix = m.group(1), m.group(2).upper()
    if not text or text in ("-", "--"):
        return None
    neg = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    if comma_decimal and "," in text and "." not in text:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if neg or suffix == "DR":
        amount = -abs(amount)
    return amount


def dedupe_hash(ledger_id: object, line: ParsedLine) -> str:
    key = "|".join([str(ledger_id), line.txn_date.isoformat(), str(line.debit.normalize()),
                    str(line.credit.normalize()), (line.reference or "").strip().upper(),
                    _norm(line.description)])  # fmt: skip
    return hashlib.sha256(key.encode()).hexdigest()


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise StatementParseError("Cannot decode the statement file")


def detect_format(data: bytes, file_name: str | None) -> str:
    head = _decode(data[:4096])
    name = (file_name or "").lower()
    if "OFXHEADER" in head.upper() or "<OFX>" in head.upper():
        return "OFX"
    if ":20:" in head and ":61:" in _decode(data):
        return "MT940"
    if name.endswith((".ofx", ".qfx")):
        return "OFX"
    if name.endswith((".sta", ".mt940", ".940")):
        return "MT940"
    return "CSV"


def parse_statement(
    data: bytes, file_name: str | None = None, *, columns: dict[str, list[str]] | None = None
) -> list[ParsedLine]:
    fmt = detect_format(data, file_name)
    text = _decode(data)
    lines = {"OFX": parse_ofx, "MT940": parse_mt940}.get(fmt, lambda t: parse_csv(t, columns))(text)
    if not lines:
        raise StatementParseError(f"No transactions found in the {fmt} statement")
    return lines


# ---------------------------------------------------------------- CSV
def _column_map(header: list[str], aliases: dict[str, list[str]]) -> dict[str, int]:
    normed = [_norm(h) for h in header]
    out: dict[str, int] = {}
    for field_name, names in aliases.items():
        for alias in names:
            a = _norm(alias)
            if a in normed and normed.index(a) not in out.values():
                out[field_name] = normed.index(a)
                break
    if "date" not in out and "value_date" in out:
        out["date"] = out["value_date"]
    return out


def parse_csv(text: str, columns: dict[str, list[str]] | None = None) -> list[ParsedLine]:
    aliases = {k: list(v) for k, v in DEFAULT_COLUMNS.items()}
    for k, extra in (columns or {}).items():
        aliases[k] = [*extra, *aliases.get(k, [])]
    raw_lines = text.splitlines()
    sample = "\n".join(raw_lines[:30])
    delimiter = max((",", ";", "\t", "|"), key=sample.count)
    comma_decimal = delimiter == ";"
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header_idx, cmap = None, {}
    for i, row in enumerate(rows[:50]):
        m = _column_map(row, aliases)
        if "date" in m and ({"debit", "credit"} & m.keys() or "amount" in m):
            header_idx, cmap = i, m
            break
    if header_idx is None:
        raise StatementParseError("Could not find a header row with date and amount columns")

    def cell(row: list[str], key: str) -> str | None:
        idx = cmap.get(key)
        return row[idx].strip() if idx is not None and idx < len(row) else None

    out: list[ParsedLine] = []
    for row in rows[header_idx + 1 :]:
        txn = parse_date(cell(row, "date"))
        if txn is None:
            continue
        debit = credit = ZERO
        if "debit" in cmap or "credit" in cmap:
            debit = abs(parse_amount(cell(row, "debit"), comma_decimal=comma_decimal) or ZERO)
            credit = abs(parse_amount(cell(row, "credit"), comma_decimal=comma_decimal) or ZERO)
        else:
            amount = parse_amount(cell(row, "amount"), comma_decimal=comma_decimal) or ZERO
            kind = (cell(row, "type") or "").upper()
            if kind.startswith(("DR", "D", "W")):
                debit = abs(amount)
            elif kind.startswith(("CR", "C")):
                credit = abs(amount)
            elif amount < 0:
                debit = -amount
            else:
                credit = amount
        if debit == 0 and credit == 0:
            continue
        balance = parse_amount(cell(row, "balance"), comma_decimal=comma_decimal)
        out.append(ParsedLine(txn, parse_date(cell(row, "value_date")) if "value_date" in cmap else None,
                              (cell(row, "description") or "").strip() or "-", cell(row, "reference") or None,
                              debit, credit, balance))  # fmt: skip
    return out


# ---------------------------------------------------------------- OFX (SGML + XML)
_OFX_BLOCK = re.compile(r"<STMTTRN>(.*?)(?=<STMTTRN>|</STMTTRN>|</BANKTRANLIST>|$)", re.S | re.I)
_OFX_TAG = re.compile(r"<(\w+)>([^<\r\n]*)")


def parse_ofx(text: str) -> list[ParsedLine]:
    out: list[ParsedLine] = []
    for block in _OFX_BLOCK.findall(text):
        tags = {k.upper(): v.strip() for k, v in _OFX_TAG.findall(block)}
        txn = parse_date((tags.get("DTPOSTED") or "")[:8])
        amount = parse_amount(tags.get("TRNAMT"))
        if txn is None or amount is None:
            continue
        desc = " ".join(x for x in (tags.get("NAME"), tags.get("MEMO")) if x) or tags.get("TRNTYPE", "-")
        ref = tags.get("CHECKNUM") or tags.get("REFNUM") or tags.get("FITID") or None
        user_date = parse_date((tags.get("DTUSER") or "")[:8])
        out.append(ParsedLine(txn, user_date, desc, ref, -amount if amount < 0 else ZERO,
                              amount if amount > 0 else ZERO, None))  # fmt: skip
    return out


# ---------------------------------------------------------------- MT940
_MT61 = re.compile(r"^(\d{6})(\d{4})?(R?[DC])([A-Z])?(\d+,\d{0,2})([A-Z][A-Z0-9]{3})([^/]*)(?://(\S*))?")


def _yymmdd(s: str) -> date:
    return date(2000 + int(s[:2]), int(s[2:4]), int(s[4:6]))


def parse_mt940(text: str) -> list[ParsedLine]:
    fields: list[list[str]] = []
    for raw in text.splitlines():
        m = re.match(r"^:(\d{2}[A-Z]?):(.*)$", raw)
        if m:
            fields.append([m.group(1), m.group(2)])
        elif fields and raw.strip() and not raw.startswith("-}"):
            fields[-1][1] += "\n" + raw.strip()
    out: list[ParsedLine] = []
    pending: dict | None = None

    def flush() -> None:
        if pending is not None:
            out.append(ParsedLine(**pending))

    for tag, value in fields:
        if tag == "61":
            flush()
            m = _MT61.match(value.split("\n")[0])
            if not m:
                pending = None
                continue
            vdate = _yymmdd(m.group(1))
            txn = vdate
            if m.group(2):
                mm, dd = int(m.group(2)[:2]), int(m.group(2)[2:])
                year = (
                    vdate.year - 1 if mm > vdate.month + 6 else vdate.year + 1 if mm + 6 < vdate.month else vdate.year
                )
                txn = date(year, mm, dd)
            amount = Decimal(m.group(5).replace(",", ".").rstrip(".") or "0")
            is_debit = m.group(3).endswith("D") != m.group(3).startswith("R")
            cust_ref = (m.group(7) or "").strip()
            ref = cust_ref if cust_ref and cust_ref.upper() != "NONREF" else (m.group(8) or None)
            pending = {"txn_date": txn, "value_date": vdate, "description": "-", "reference": ref,
                       "debit": amount if is_debit else ZERO, "credit": ZERO if is_debit else amount,
                       "balance": None}  # fmt: skip
        elif tag == "86" and pending is not None:
            pending["description"] = re.sub(r"\s+", " ", value.replace("\n", " ")).strip() or "-"
    flush()
    return out
