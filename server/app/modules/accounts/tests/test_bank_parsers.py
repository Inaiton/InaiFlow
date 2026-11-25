"""Bank statement parsers (pure)."""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.accounts.bank_parsers import StatementParseError, detect_format, parse_statement

D = Decimal

CSV_HDFC = """HDFC BANK Ltd. Statement of account
Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/09/26,NEFT-ACME STEEL,000123,01/09/26,"2,50,000.00",,"7,50,000.00"
03/09/26,CHQ DEP 445566,445566,04/09/26,,"1,18,000.00","8,68,000.00"

Statement summary,,,,,,
"""

CSV_SIGNED = """Txn Date;Description;Reference;Amount;Dr/Cr;Balance
2026-09-05;Bank charges;;-118,00;DR;
"""

CSV_SINGLE_AMOUNT = """Transaction Date,Particulars,Cheque No,Amount,Type,Balance
05-Sep-2026,UPI/ABC,,"500.50",CR,1000.00
06-Sep-2026,ATM WDL,,"200",DR,800.00
"""

OFX_SGML = """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>INR
<BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260901120000[+5.5:IST]<TRNAMT>-250000.00<FITID>A1<CHECKNUM>000123<NAME>ACME STEEL<MEMO>NEFT
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260903<TRNAMT>118000<FITID>A2<NAME>CHQ DEP
</BANKTRANLIST>
<LEDGERBAL><BALAMT>868000<DTASOF>20260930
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""

OFX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<?OFX OFXHEADER="200" VERSION="220"?>
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260910</DTPOSTED><TRNAMT>-99.50</TRNAMT><FITID>X9</FITID><NAME>Fee</NAME></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""

MT940 = """:20:STMT2609
:25:HDFC0001234/50100012345678
:28C:00001/001
:60F:C260831INR500000,00
:61:2609010901D250000,00NTRF000123//HDFCREF1
:86:NEFT ACME STEEL
 PVT LTD
:61:260904C118000,NCHK445566
:86:CHQ DEP
:62F:C260930INR368000,00
"""


def test_csv_common_bank_columns():
    lines = parse_statement(CSV_HDFC.encode(), "hdfc.csv")
    assert len(lines) == 2
    a, b = lines
    assert a.txn_date == date(2026, 9, 1) and a.debit == D("250000.00") and a.credit == D("0")
    assert a.reference == "000123" and a.balance == D("750000.00") and a.description == "NEFT-ACME STEEL"
    assert b.value_date == date(2026, 9, 4) and b.credit == D("118000.00")


def test_csv_semicolon_signed_amount_with_comma_decimal():
    (line,) = parse_statement(CSV_SIGNED.encode(), "x.csv")
    assert line.debit == D("118.00") and line.credit == D("0") and line.txn_date == date(2026, 9, 5)


def test_csv_single_amount_with_type_column():
    a, b = parse_statement(CSV_SINGLE_AMOUNT.encode(), "x.csv")
    assert a.credit == D("500.50") and a.txn_date == date(2026, 9, 5)
    assert b.debit == D("200")


def test_csv_custom_column_mapping():
    data = b"When,What,Out,In\n2026-09-01,Rent,1000,\n"
    (line,) = parse_statement(data, "x.csv", columns={"date": ["when"], "description": ["what"],
                                                         "debit": ["out"], "credit": ["in"]})  # fmt: skip
    assert line.debit == D("1000")


def test_ofx_sgml():
    lines = parse_statement(OFX_SGML.encode(), "s.ofx")
    assert [ln.txn_date for ln in lines] == [date(2026, 9, 1), date(2026, 9, 3)]
    assert lines[0].debit == D("250000.00") and lines[0].reference == "000123"
    assert lines[1].credit == D("118000")
    assert "ACME STEEL" in lines[0].description


def test_ofx_xml():
    (line,) = parse_statement(OFX_XML.encode(), "s.ofx")
    assert line.debit == D("99.50") and line.reference == "X9"


def test_mt940():
    lines = parse_statement(MT940.encode(), "s.sta")
    assert len(lines) == 2
    a, b = lines
    assert a.value_date == date(2026, 9, 1) and a.txn_date == date(2026, 9, 1)
    assert a.debit == D("250000.00") and a.reference == "000123"
    assert a.description == "NEFT ACME STEEL PVT LTD"
    assert b.credit == D("118000") and b.txn_date == date(2026, 9, 4)


def test_detect_format():
    assert detect_format(OFX_SGML.encode(), "a.txt") == "OFX"
    assert detect_format(MT940.encode(), "a.txt") == "MT940"
    assert detect_format(CSV_HDFC.encode(), "a.csv") == "CSV"


def test_garbage_raises():
    with pytest.raises(StatementParseError):
        parse_statement(b"hello world\nno columns here\n", "a.csv")
