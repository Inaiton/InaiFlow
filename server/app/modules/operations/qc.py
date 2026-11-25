"""Pure QC logic: readings (incl. Quick QC autofill), tolerance checks, pass-criteria evaluation and a tiny
safe expression language (comparisons, and/or/not, numbers, booleans, field names). Never uses eval().
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

CRITERIA_MODES = frozenset({"ALL_FIELDS_IN_TOLERANCE", "ALL_IN_TOLERANCE", "ACCEPTED_GT_ZERO", "EXPRESSION", "MANUAL"})
_TRUE = {"true", "yes", "1", "ok", "pass", "y"}
_FALSE = {"false", "no", "0", "nok", "fail", "n"}


class ExpressionError(ValueError):
    pass


class ReadingError(ValueError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


# ---------------------------------------------------------------- readings
def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ReadingError(f"'{value}' is not a number") from exc


def _bool(value: str) -> bool | None:
    v = value.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None


def in_tolerance(field: dict[str, Any], value: str | None) -> bool | None:
    """True/False when the field has an acceptance rule, None when it is informational."""
    if value is None:
        return None
    ftype = str(field.get("type") or "NUMBER").upper()
    if ftype == "NUMBER":
        v = _dec(value)
        nominal = _dec(field.get("nominal"))
        if nominal is None or v is None:
            return None
        lo = nominal - (_dec(field.get("tol_minus")) or Decimal(0))
        hi = nominal + (_dec(field.get("tol_plus")) or Decimal(0))
        return lo <= v <= hi
    if ftype == "BOOL":
        b = _bool(value)
        if b is None:
            raise ReadingError(f"'{value}' is not a yes/no value", field.get("key"))
        return b
    if ftype == "SELECT" and field.get("options"):
        return value in field["options"]
    return None


def build_readings(
    qc_fields: list[dict[str, Any]], measurements: dict[str, Any] | None, *, quick_qc: bool
) -> dict[str, dict[str, Any]]:
    """Readings keyed by field: ``{value, in_tolerance, auto_filled}``.

    Quick QC: when ``quick_qc`` is set, or a measurement is omitted for a field with a nominal, the nominal
    is filled in (``auto_filled=True``, ``in_tolerance=True``); BOOL fields are filled with ``true`` only in
    quick-QC mode. Required fields still missing raise ``ReadingError`` (unless quick QC).
    """
    measurements = dict(measurements or {})
    known = {f.get("key") for f in qc_fields}
    unknown = sorted(k for k in measurements if k not in known)
    if unknown:
        raise ReadingError(f"Unknown QC fields: {', '.join(unknown)}", unknown[0])
    out: dict[str, dict[str, Any]] = {}
    for f in qc_fields:
        key = f["key"]
        raw = measurements.get(key)
        raw = None if raw is None or str(raw).strip() == "" else str(raw).strip()
        ftype = str(f.get("type") or "NUMBER").upper()
        if raw is None and f.get("nominal") not in (None, "") and (quick_qc or key not in measurements):
            out[key] = {"value": str(f["nominal"]), "in_tolerance": True, "auto_filled": True}
            continue
        if raw is None and quick_qc and ftype == "BOOL":
            out[key] = {"value": "true", "in_tolerance": True, "auto_filled": True}
            continue
        if raw is None:
            if f.get("required") and not quick_qc:
                raise ReadingError(f"'{f.get('label') or key}' is required", key)
            out[key] = {"value": None, "in_tolerance": None, "auto_filled": False}
            continue
        try:
            tol = in_tolerance(f, raw)
        except ReadingError as exc:
            raise ReadingError(f"{f.get('label') or key}: {exc}", key) from exc
        out[key] = {"value": raw, "in_tolerance": tol, "auto_filled": False}
    return out


def nominal_readings(qc_fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return build_readings(qc_fields, None, quick_qc=True)


# ---------------------------------------------------------------- expression language
_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+(?:\.\d+)?)|(?P<op><=|>=|==|!=|<|>|&&|\|\||!|\(|\)|-)|(?P<name>[A-Za-z_][A-Za-z0-9_]*))"
)


def _tokenize(src: str) -> list[tuple[str, str]]:
    pos, out = 0, []
    src = src.rstrip()
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise ExpressionError(f"unexpected character at position {pos + 1}")
        pos = m.end()
        kind = m.lastgroup or ""
        val = m.group(kind)
        if kind == "name" and val.lower() in ("and", "or", "not", "true", "false"):
            kind, val = ("op", val.lower()) if val.lower() in ("and", "or", "not") else ("bool", val.lower())
        out.append((kind, {"&&": "and", "||": "or", "!": "not"}.get(val, val)))
    return out


@dataclass(frozen=True, slots=True)
class Node:
    kind: str  # num | bool | name | not | and | or | cmp
    value: Any = None
    children: tuple[Node, ...] = ()

    def names(self) -> set[str]:
        own = {self.value} if self.kind == "name" else set()
        for c in self.children:
            own |= c.names()
        return own


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.t, self.i = tokens, 0

    def peek(self) -> tuple[str, str] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise ExpressionError("unexpected end of expression")
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self.or_()
        if self.peek() is not None:
            raise ExpressionError(f"unexpected '{self.peek()[1]}'")  # type: ignore[index]
        return node

    def or_(self) -> Node:
        node = self.and_()
        while self.peek() == ("op", "or"):
            self.take()
            node = Node("or", children=(node, self.and_()))
        return node

    def and_(self) -> Node:
        node = self.not_()
        while self.peek() == ("op", "and"):
            self.take()
            node = Node("and", children=(node, self.not_()))
        return node

    def not_(self) -> Node:
        if self.peek() == ("op", "not"):
            self.take()
            return Node("not", children=(self.not_(),))
        return self.cmp()

    def cmp(self) -> Node:
        left = self.atom()
        tok = self.peek()
        if tok and tok[0] == "op" and tok[1] in ("<", "<=", ">", ">=", "==", "!="):
            self.take()
            return Node("cmp", tok[1], (left, self.atom()))
        return left

    def atom(self) -> Node:
        kind, val = self.take()
        if kind == "num":
            return Node("num", Decimal(val))
        if kind == "op" and val == "-":
            k2, v2 = self.take()
            if k2 != "num":
                raise ExpressionError("'-' must be followed by a number")
            return Node("num", -Decimal(v2))
        if kind == "bool":
            return Node("bool", val == "true")
        if kind == "name":
            return Node("name", val)
        if (kind, val) == ("op", "("):
            node = self.or_()
            if self.take() != ("op", ")"):
                raise ExpressionError("missing ')'")
            return node
        raise ExpressionError(f"unexpected '{val}'")


def parse_expression(src: str) -> Node:
    if not src or len(src) > 1000:
        raise ExpressionError("expression must be 1-1000 characters")
    depth = 0
    for ch in src:  # bound recursion: deep nesting would raise RecursionError (500) in the parser
        depth += (ch == "(") - (ch == ")")
        if depth > 20:
            raise ExpressionError("expression is nested too deeply")
    return _Parser(_tokenize(src)).parse()


def _truthy(v: Any) -> bool:
    return bool(v) if v is not None else False


def _eval(node: Node, env: dict[str, Any]) -> Any:
    if node.kind in ("num", "bool"):
        return node.value
    if node.kind == "name":
        return env.get(node.value)
    if node.kind == "not":
        return not _truthy(_eval(node.children[0], env))
    if node.kind == "and":
        return _truthy(_eval(node.children[0], env)) and _truthy(_eval(node.children[1], env))
    if node.kind == "or":
        return _truthy(_eval(node.children[0], env)) or _truthy(_eval(node.children[1], env))
    a, b = (_eval(c, env) for c in node.children)
    if a is None or b is None:
        return False
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    op = node.value
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if isinstance(a, bool):
        raise ExpressionError(f"cannot order yes/no values with '{op}'")
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


def _env_value(reading: dict[str, Any], field: dict[str, Any] | None) -> Any:
    value = reading.get("value")
    if value is None:
        return None
    ftype = str((field or {}).get("type") or "NUMBER").upper()
    if ftype == "BOOL":
        return _bool(str(value))
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def evaluate_expression(src: str, env: dict[str, Any]) -> bool:
    return _truthy(_eval(parse_expression(src), env))


def evaluate_pass_criteria(
    criteria: dict[str, Any] | None,
    readings: dict[str, dict[str, Any]],
    *,
    qc_fields: list[dict[str, Any]] | None = None,
    accepted: Decimal = Decimal(0),
    rejected: Decimal = Decimal(0),
    rework: Decimal = Decimal(0),
    input_qty: Decimal = Decimal(0),
) -> bool:
    mode = str((criteria or {}).get("mode") or "ALL_FIELDS_IN_TOLERANCE").upper()
    if mode in ("ALL_FIELDS_IN_TOLERANCE", "ALL_IN_TOLERANCE"):
        return all(r.get("in_tolerance") is not False for r in readings.values())
    if mode == "ACCEPTED_GT_ZERO":
        return accepted > 0
    if mode == "MANUAL":
        return True
    if mode == "EXPRESSION":
        fields = {f["key"]: f for f in qc_fields or []}
        env: dict[str, Any] = {k: _env_value(r, fields.get(k)) for k, r in readings.items()}
        env.update(accepted=accepted, rejected=rejected, rework=rework, input=input_qty)
        return evaluate_expression(str((criteria or {}).get("expression") or ""), env)
    raise ExpressionError(f"unknown pass criteria mode '{mode}'")
