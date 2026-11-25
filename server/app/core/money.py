"""Decimal helpers. Money/qty are ``Decimal`` everywhere and JSON strings on the wire (never floats)."""

from __future__ import annotations

import re
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema

ZERO = Decimal("0")
FOUR = Decimal("0.0001")
TWO = Decimal("0.01")
ONE = Decimal("1")
DECIMAL_PATTERN = r"^-?\d+(\.\d{1,4})?$"
_DECIMAL_RE = re.compile(DECIMAL_PATTERN)


def D(value: Any) -> Decimal:  # noqa: N802 - conventional short constructor
    """Build a Decimal from str/int/Decimal. Floats are rejected (use strings)."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not a decimal")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        raise TypeError("floats are not allowed for money/quantity; pass a string")
    if value is None:
        raise TypeError("None is not a decimal")
    try:
        return Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal: {value!r}") from exc


def q4(value: Any) -> Decimal:
    """Quantize to 4 places (NUMERIC(18,4)), half-up."""
    return D(value).quantize(FOUR, rounding=ROUND_HALF_UP)


def q2(value: Any) -> Decimal:
    return D(value).quantize(TWO, rounding=ROUND_HALF_UP)


def round_rupee(value: Any) -> Decimal:
    """Nearest rupee, half-up (GST invoice round-off)."""
    return D(value).quantize(ONE, rounding=ROUND_HALF_UP)


def ceil_rupee(value: Any) -> Decimal:
    """Round up to the next rupee (ESIC employee share)."""
    return D(value).quantize(ONE, rounding=ROUND_CEILING)


def pct(base: Any, rate_pct: Any) -> Decimal:
    """``base * rate_pct / 100`` quantized to 4 places."""
    return q4(D(base) * D(rate_pct) / Decimal(100))


def to_str(value: Decimal | int | str | None) -> str | None:
    """Wire format: up to 4 decimals, no exponent, no trailing zeros beyond 2 places kept.

    ``Decimal('1E+2')`` -> ``'100.00'``; ``Decimal('2.5')`` -> ``'2.50'``; ``Decimal('0.1234')`` -> ``'0.1234'``.
    """
    if value is None:
        return None
    d = q4(value)
    text = format(d, "f")
    if "." in text:
        whole, frac = text.split(".")
        frac = frac.rstrip("0")
        frac = frac.ljust(2, "0")
        text = f"{whole}.{frac}"
    else:
        text = f"{text}.00"
    if text.startswith("-") and D(text) == 0:
        text = text[1:]
    return text


def _validate_decimal(value: Any) -> Decimal:
    if isinstance(value, float):
        raise ValueError("decimal values must be sent as strings, not floats")
    if isinstance(value, str):
        if not _DECIMAL_RE.match(value.strip()):
            raise ValueError("must be a decimal string with at most 4 decimal places")
        return Decimal(value.strip())
    d = D(value)
    if d != d.quantize(FOUR):
        raise ValueError("at most 4 decimal places are allowed")
    return d


_SCHEMA = {"type": "string", "pattern": DECIMAL_PATTERN, "format": "decimal"}

#: Pydantic field type for money/qty/rates: accepts "12.50" / 12 / Decimal, rejects floats, serializes as str.
DecimalStr = Annotated[
    Decimal,
    BeforeValidator(_validate_decimal),
    PlainSerializer(lambda d: to_str(d), return_type=str),
    WithJsonSchema(_SCHEMA),
]
