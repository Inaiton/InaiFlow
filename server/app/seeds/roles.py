"""Default role matrices (DEFAULT_ROLES config). Keys missing from a matrix mean NONE."""

from app.core.permissions import ALL_PERMISSION_KEYS


def _all(level: str) -> dict[str, str]:
    return dict.fromkeys(ALL_PERMISSION_KEYS, level)


def _with(base: dict[str, str], **overrides: str) -> dict[str, str]:
    out = dict(base)
    for k, v in overrides.items():
        out[k.replace("__", ".")] = v
    return out


_NONE = _all("NONE")

ORG_OWNER = _all("FULL")
ADMIN = _with(_all("FULL"), organization__billing="READ")
ACCOUNTANT = _with(
    _NONE,
    accounts__dashboard="FULL", accounts__vouchers="FULL", accounts__ledgers_groups="FULL",
    accounts__inventory_masters="WRITE", accounts__banking="FULL", accounts__payroll_employees="WRITE",
    accounts__payroll_runs="FULL", accounts__taxation="FULL", accounts__reports="FULL",
    operations__dashboard="READ", operations__items="READ", operations__runs_execution="READ",
    operations__runs_accounting="WRITE",
    documents__explorer="WRITE", documents__capture_upload="WRITE", documents__editor="READ",
    documents__templates="READ",
    organization__profile="READ", organization__audit_logs="READ",
)  # fmt: skip
QA_LEAD = _with(
    _NONE,
    **{f"operations__{k}": "FULL" for k in ("dashboard", "items", "workflows", "runs_execution",
                                            "runs_accounting", "qc_signoff", "iso_compliance")},
    documents__explorer="FULL", documents__capture_upload="FULL", documents__editor="FULL",
    documents__iso_approval="FULL", documents__templates="WRITE",
    organization__profile="READ",
)  # fmt: skip
OPERATOR = _with(
    _NONE,
    operations__dashboard="READ", operations__items="READ", operations__runs_execution="WRITE",
    documents__capture_upload="WRITE", documents__explorer="READ",
)  # fmt: skip
AUDITOR = _with(
    _NONE,
    **{f"operations__{k}": "READ" for k in ("dashboard", "items", "workflows", "runs_execution",
                                            "qc_signoff", "iso_compliance")},
    documents__explorer="READ",
)  # fmt: skip

DEFAULT_ROLES: list[dict] = [
    {
        "role_code": "ORG_OWNER",
        "role_name": "Organization Owner",
        "is_external_collaborator": False,
        "permissions": ORG_OWNER,
    },
    {"role_code": "ADMIN", "role_name": "Administrator", "is_external_collaborator": False, "permissions": ADMIN},
    {
        "role_code": "ACCOUNTANT",
        "role_name": "Accountant",
        "is_external_collaborator": False,
        "permissions": ACCOUNTANT,
    },
    {"role_code": "QA_LEAD", "role_name": "QA Lead", "is_external_collaborator": False, "permissions": QA_LEAD},
    {
        "role_code": "OPERATOR",
        "role_name": "Shop-floor Operator",
        "is_external_collaborator": False,
        "permissions": OPERATOR,
    },
    {
        "role_code": "AUDITOR",
        "role_name": "External ISO Auditor",
        "is_external_collaborator": True,
        "permissions": AUDITOR,
    },
]
