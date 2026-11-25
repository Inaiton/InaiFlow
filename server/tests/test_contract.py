"""Contract conformance: every implemented contract operation exists with the same method, path and guard.

``test_contract_complete`` stays xfail until all streams land; it prints the missing operations by module.
"""

import json
from collections import defaultdict
from pathlib import Path

import pytest

INDEX = Path(__file__).resolve().parents[2] / "docs" / "api" / "contract_index.json"


def _contract() -> list[dict]:
    return json.loads(INDEX.read_text())


def _app_ops(app) -> dict[tuple[str, str], tuple[str, str | None, list[str] | None]]:  # noqa: ANN001
    from app.main import iter_api_routes, route_guard

    ops = {}
    for path, methods, route in iter_api_routes(app):
        for m in methods - {"HEAD", "OPTIONS"}:
            ops[(m, path)] = route_guard(route)
    return ops


def _module_of(path: str) -> str:
    parts = path.removeprefix("/api/v1/").split("/")
    if parts[0] == "accounts" and len(parts) > 1 and parts[1] in ("payroll", "taxation"):
        return parts[1]
    return parts[0]


def test_implemented_operations_match_contract(app):
    ops = _app_ops(app)
    contract = {(c["method"], c["path"]): c for c in _contract()}
    mismatches = []
    for key, c in contract.items():
        if key not in ops:
            continue
        auth, perm, roles = ops[key]
        if auth != c["auth"]:
            mismatches.append(f"{key}: auth {auth} != {c['auth']}")
        if c["auth"] == "org" and perm != c["permission"]:
            mismatches.append(f"{key}: permission {perm} != {c['permission']}")
        if c["auth"] == "admin" and sorted(roles or []) != sorted(c["admin_roles"] or []):
            mismatches.append(f"{key}: admin roles {roles} != {c['admin_roles']}")
    assert not mismatches, "\n".join(mismatches)


def test_no_undeclared_api_routes(app):
    contract = {(c["method"], c["path"]) for c in _contract()}
    extra = [k for k in _app_ops(app) if k not in contract]
    assert not extra, f"routes not in the contract: {extra}"


def test_s1_scope_complete(app):
    ops = _app_ops(app)
    s1 = ("health", "meta", "internal", "auth", "me", "organizations", "org", "organization", "storage")
    missing = [(c["method"], c["path"]) for c in _contract()
               if _module_of(c["path"]) in s1 and (c["method"], c["path"]) not in ops]  # fmt: skip
    assert not missing, missing


@pytest.mark.xfail(strict=False, reason="other streams (S2-S5) still landing")
def test_contract_complete(app):
    ops = _app_ops(app)
    missing: dict[str, list[str]] = defaultdict(list)
    for c in _contract():
        if (c["method"], c["path"]) not in ops:
            missing[_module_of(c["path"])].append(f"{c['method']} {c['path']}")
    total = len(_contract())
    done = total - sum(len(v) for v in missing.values())
    print(f"\ncontract coverage: {done}/{total}")
    for mod, items in sorted(missing.items()):
        print(f"  {mod}: {len(items)} missing")
    assert not missing
