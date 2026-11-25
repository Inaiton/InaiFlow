"""Pure seed data. ``config_rows()`` = every ``platform_global_configs`` row (category, key, name, payload).

Loaded by migration 0001 (data step) and ``python -m app.cli seed-configs`` (inserts missing rows only).
"""

from __future__ import annotations

from datetime import date

from app.seeds.account_groups import ACCOUNT_GROUPS
from app.seeds.default_ledgers import DEFAULT_LEDGERS, SYSTEM_GODOWNS
from app.seeds.doc_templates import DOC_REPORT_TEMPLATES
from app.seeds.folder_templates import DEFAULT_MONTHLY_RULE, MASTER_LIBRARY, MONTHLY_SUBFOLDERS
from app.seeds.iso_checklist import ISO_9001_2015_CHECKLIST
from app.seeds.iso_workflows import ISO_WORKFLOW_TEMPLATES
from app.seeds.plans import FEATURE_FLAGS, PLANS
from app.seeds.roles import DEFAULT_ROLES
from app.seeds.states import INDIAN_STATES
from app.seeds.tax_rules import EPF, ESIC, GST_SLABS, INCOME_TAX, PT_SLABS, TDS_SECTIONS
from app.seeds.uom import UOMS
from app.seeds.voucher_types import VOUCHER_TYPES

SEED_EFFECTIVE_FROM = date(2025, 4, 1)

# Config keys other modules rely on (category -> keys)
DEFAULT_KEY = "default"


def config_rows() -> list[dict]:
    rows: list[dict] = [
        {"category": "ACCOUNT_GROUPS", "key": DEFAULT_KEY, "name": "28 Tally account groups",
         "payload": {"groups": ACCOUNT_GROUPS}},
        {"category": "DEFAULT_LEDGERS", "key": DEFAULT_KEY, "name": "Default ledgers & system godowns",
         "payload": {"ledgers": DEFAULT_LEDGERS, "godowns": SYSTEM_GODOWNS}},
        {"category": "VOUCHER_TYPES", "key": DEFAULT_KEY, "name": "Voucher types",
         "payload": {"voucher_types": VOUCHER_TYPES}},
        {"category": "GST_SLABS", "key": DEFAULT_KEY, "name": "GST rate slabs & thresholds", "payload": GST_SLABS},
        {"category": "TDS_SECTIONS", "key": DEFAULT_KEY, "name": "TDS / TCS sections", "payload": TDS_SECTIONS},
        {"category": "PAYROLL_STATUTORY", "key": "EPF", "name": "EPF / EPS / EDLI / admin charges", "payload": EPF},
        {"category": "PAYROLL_STATUTORY", "key": "ESIC", "name": "ESIC", "payload": ESIC},
        {"category": "PAYROLL_STATUTORY", "key": "PT_SLABS", "name": "Professional tax slabs", "payload": PT_SLABS},
        {"category": "PAYROLL_STATUTORY", "key": "INCOME_TAX", "name": "Income tax slabs FY 2025-26",
         "payload": INCOME_TAX},
        {"category": "FOLDER_TEMPLATES", "key": "MONTHLY", "name": "Monthly system subfolders",
         "payload": {"subfolders": MONTHLY_SUBFOLDERS}},
        {"category": "FOLDER_TEMPLATES", "key": "MASTER_LIBRARY", "name": "Master Library tree",
         "payload": MASTER_LIBRARY},
        {"category": "ISO_CHECKLIST", "key": "ISO_9001_2015", "name": "ISO 9001:2015 checklist",
         "payload": {"items": ISO_9001_2015_CHECKLIST}},
        {"category": "UOM", "key": DEFAULT_KEY, "name": "Units of measure", "payload": {"uoms": UOMS}},
        {"category": "INDIAN_STATES", "key": DEFAULT_KEY, "name": "GST state codes", "payload": {"states": INDIAN_STATES}},
        {"category": "FEATURE_FLAGS", "key": DEFAULT_KEY, "name": "Feature flags", "payload": FEATURE_FLAGS},
    ]  # fmt: skip
    rows += [
        {"category": "ISO_WORKFLOW_TEMPLATES", "key": t["key"], "name": t["name"], "payload": t}
        for t in ISO_WORKFLOW_TEMPLATES
    ]
    rows += [
        {"category": "DOC_REPORT_TEMPLATES", "key": t["key"], "name": t["name"], "payload": t}
        for t in DOC_REPORT_TEMPLATES
    ]
    rows += [
        {"category": "DEFAULT_ROLES", "key": r["role_code"], "name": r["role_name"], "payload": r}
        for r in DEFAULT_ROLES
    ]
    return rows


__all__ = [
    "DEFAULT_KEY",
    "DEFAULT_MONTHLY_RULE",
    "PLANS",
    "SEED_EFFECTIVE_FROM",
    "config_rows",
]
