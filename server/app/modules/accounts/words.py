"""Amount in words, Indian numbering (crore / lakh / thousand)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]  # fmt: skip
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(f"{_ONES[n // 100]} Hundred")
    if n % 100:
        parts.append(_two(n % 100))
    return " ".join(parts)


def number_in_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    if crore:
        parts.append(f"{number_in_words(crore)} Crore")
    if lakh:
        parts.append(f"{_two(lakh)} Lakh")
    if thousand:
        parts.append(f"{_two(thousand)} Thousand")
    if n:
        parts.append(_three(n))
    return " ".join(parts)


def amount_in_words(amount: Decimal, currency: str = "Rupees", sub: str = "Paise") -> str:
    value = abs(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, frac = int(value), int((value - int(value)) * 100)
    text = f"{currency} {number_in_words(whole)}"
    if frac:
        text += f" and {_two(frac)} {sub}"
    return text + " Only"
