"""Permission catalog + pure resolution logic (4-tier RBAC and record-level ACL semantics).

Levels are ordered ``NONE < READ < WRITE < FULL``. ``ORG_OWNER`` is always FULL. A ``resource_acl`` row for
the USER wins over a row for the user's ROLE; either replaces the module level for that one resource
(it may raise or lower it).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal

Level = Literal["NONE", "READ", "WRITE", "FULL"]
LEVELS: tuple[str, ...] = ("NONE", "READ", "WRITE", "FULL")
_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}

RESOURCE_TYPES: tuple[str, ...] = ("STOCK_ITEM", "PERIOD_RUN", "DOC_FOLDER", "GODOWN")

PERMISSION_CATALOG: list[dict] = [
    {
        "module": "accounts",
        "label": "Accounts",
        "keys": [
            ("dashboard", "Dashboard", "Accounts dashboard, KPIs and alerts"),
            ("vouchers", "Vouchers", "Create, edit, cancel and print vouchers; voucher types; accounts settings"),
            ("ledgers_groups", "Ledgers & Groups", "Chart of accounts, cost centres, currencies"),
            ("inventory_masters", "Inventory Masters", "Stock items, stock groups, godowns, BOM, stock reports"),
            ("banking", "Banking", "Bank reconciliation, statement import, cheques"),
            ("payroll_employees", "Payroll Employees", "Employee master and salary structures"),
            ("payroll_runs", "Payroll Runs", "Attendance, payroll runs, lock, payslips, statutory files"),
            ("taxation", "Taxation", "GST returns, e-invoice, e-way bill, TDS/TCS"),
            ("reports", "Reports", "Financial statements, day book, ageing, exports"),
        ],
    },
    {
        "module": "operations",
        "label": "Operations",
        "keys": [
            ("dashboard", "Dashboard", "Operations dashboard"),
            ("items", "Items", "Stock items and process targets in Operations"),
            ("workflows", "Workflows", "ISO process flowcharts, versions and publishing"),
            ("runs_execution", "Run Execution", "Launch period runs and execute steps"),
            ("runs_accounting", "Run Accounting", "Money flow, Dr/Cr postings and linked vouchers in runs"),
            ("qc_signoff", "QC Sign-off", "Sign off and lock QC steps; overrides"),
            ("iso_compliance", "ISO Compliance", "NCR/CAPA, calibration, ISO checklist, auditor invites"),
        ],
    },
    {
        "module": "documents",
        "label": "Documents",
        "keys": [
            ("explorer", "Explorer", "Browse, preview, download and delete documents"),
            ("capture_upload", "Capture & Upload", "Upload, scan and organise folders"),
            ("editor", "Editor", "Create and edit internal documents and reports"),
            ("iso_approval", "ISO Approval", "Review and approve controlled documents"),
            ("templates", "Templates", "Report templates and monthly folder rules"),
        ],
    },
    {
        "module": "organization",
        "label": "Organization",
        "keys": [
            ("profile", "Profile", "Company profile, branches, logo and stamp"),
            ("members", "Members", "Members, invitations and join requests"),
            ("roles_rbac", "Roles & Access", "Roles, permission matrix and resource ACLs"),
            ("security_policies", "Security Policies", "2FA, session and approval policies"),
            ("audit_logs", "Audit Logs", "Organization audit trail"),
            ("billing", "Billing", "Plan, seats and storage"),
        ],
    },
]

ALL_PERMISSION_KEYS: tuple[str, ...] = tuple(f"{m['module']}.{k[0]}" for m in PERMISSION_CATALOG for k in m["keys"])
_KEYSET = frozenset(ALL_PERMISSION_KEYS)

IMPERSONATION_FULL_EXCLUDED = ("organization.billing", "organization.roles_rbac", "organization.members")


def is_valid_level(value: object) -> bool:
    return isinstance(value, str) and value in _RANK


def is_valid_key(key: str) -> bool:
    return key in _KEYSET


def level_rank(level: str) -> int:
    return _RANK.get(level, 0)


def at_least(have: str, need: str) -> bool:
    return level_rank(have) >= level_rank(need)


def max_level(levels: Iterable[str]) -> str:
    best = "NONE"
    for lvl in levels:
        if level_rank(lvl) > level_rank(best):
            best = lvl
    return best


def effective_permissions(role_permissions: Mapping[str, object] | None, *, is_owner: bool) -> dict[str, str]:
    """Full map over every catalog key. Missing/invalid -> NONE; unknown keys dropped; owner -> FULL."""
    if is_owner:
        return dict.fromkeys(ALL_PERMISSION_KEYS, "FULL")
    perms = role_permissions or {}
    out: dict[str, str] = {}
    for key in ALL_PERMISSION_KEYS:
        value = perms.get(key)
        out[key] = value if is_valid_level(value) else "NONE"  # type: ignore[assignment]
    return out


def effective_level(role_permissions: Mapping[str, object] | None, key: str, *, is_owner: bool) -> str:
    if is_owner:
        return "FULL"
    value = (role_permissions or {}).get(key)
    return value if is_valid_level(value) else "NONE"  # type: ignore[return-value]


def resolve_resource_level(
    module_level: str, *, user_override: str | None, role_override: str | None, is_owner: bool
) -> str:
    if is_owner:
        return "FULL"
    if user_override is not None:
        return user_override
    if role_override is not None:
        return role_override
    return module_level


def impersonation_permissions(mode: str) -> dict[str, str]:
    if mode == "FULL_SUPPORT":
        perms = dict.fromkeys(ALL_PERMISSION_KEYS, "FULL")
        for key in IMPERSONATION_FULL_EXCLUDED:
            perms[key] = "READ"
        return perms
    return dict.fromkeys(ALL_PERMISSION_KEYS, "READ")


def validate_permission_map(perms: Mapping[str, object]) -> dict[str, str]:
    """Strict validation for user-supplied role matrices (raises ValueError)."""
    out: dict[str, str] = {}
    for key, value in perms.items():
        if key not in _KEYSET:
            raise ValueError(f"unknown permission key: {key}")
        if not is_valid_level(value):
            raise ValueError(f"invalid level for {key}: {value!r}")
        out[key] = value  # type: ignore[assignment]
    return out
