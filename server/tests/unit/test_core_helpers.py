import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.adapters.export import Letterhead, Report, get_exporter
from app.adapters.storage import build_org_key, sanitize_name
from app.adapters.taxgateway import MockTaxGateway
from app.core.audit import diff, to_jsonable
from app.core.money import D, DecimalStr, ceil_rupee, q4, round_rupee, to_str
from app.core.sequences import format_number


class M(BaseModel):
    amount: DecimalStr


def test_decimal_str_type():
    assert M(amount="12.5").model_dump(mode="json") == {"amount": "12.50"}
    assert M(amount=7).amount == Decimal(7)
    with pytest.raises(ValidationError):
        M(amount=1.5)
    with pytest.raises(ValidationError):
        M(amount="1.23456")
    assert M.model_json_schema()["properties"]["amount"]["type"] == "string"


def test_money_helpers():
    assert q4("1.00005") == Decimal("1.0001")
    assert round_rupee("10.5") == 11 and ceil_rupee("112.01") == 113
    assert (
        to_str(Decimal("1E+2")) == "100.00"
        and to_str(Decimal("-0")) == "0.00"
        and to_str(Decimal("0.1234")) == "0.1234"
    )
    with pytest.raises(TypeError):
        D(0.1)


def test_audit_json_and_diff():
    u = uuid.uuid4()
    assert to_jsonable({"a": Decimal("2.5"), "u": u, "d": date(2026, 4, 1)}) == {
        "a": "2.50",
        "u": str(u),
        "d": "2026-04-01",
    }
    assert diff({"a": 1, "b": 2}, {"a": 1, "b": 3}) == ({"b": 2}, {"b": 3})


def test_storage_keys():
    assert sanitize_name("../../etc/passwd") == "passwd"
    assert sanitize_name("Bill #1 (final).pdf") == "Bill_1_final_.pdf"
    org = uuid.uuid4()
    key = build_org_key(org, "inv.pdf", date(2026, 9, 3))
    assert key.startswith(f"org/{org}/2026/09/") and key.endswith("/inv.pdf")
    assert format_number("SI/", 7, 4) == "SI/0007"


def test_export_pdf_docx_unicode():
    r = Report("Batch ₹ Summary", [{"type": "heading", "data": {"text": "Costs", "level": 2}},
                                    {"type": "kv", "data": {"rows": [{"label": "Unit cost", "value": "₹ 125.50"}]}},
                                    {"type": "table", "data": {"columns": ["a", "b"], "rows": [["1", "2"]]}},
                                    {"type": "signature", "data": {"roles": ["QA Lead"]}}],
               Letterhead("Acme Pvt Ltd", ["Coimbatore"]), watermark="OBSOLETE")  # fmt: skip
    assert get_exporter().render(r, "pdf")[:5] == b"%PDF-"
    assert get_exporter().render(r, "docx")[:2] == b"PK"


async def test_mock_tax_gateway_is_deterministic():
    g = MockTaxGateway()
    p = {"SellerDtls": {"Gstin": "33ABCDE1234F1Z5"}, "DocDtls": {"Typ": "INV", "No": "SI/0001", "Dt": "01/09/2026"}}
    a, b = await g.generate_irn(p), await g.generate_irn(p)
    assert a.irn == b.irn and len(a.irn) == 64 and a.ack_no == b.ack_no
    e = await g.generate_eway_bill({"distance_km": 450})
    assert len(e.eway_bill_no) == 12
