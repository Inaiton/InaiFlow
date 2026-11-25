"""Folder blueprints: monthly system subfolders and the Master Library tree."""

MONTHLY_SUBFOLDERS: list[dict] = [
    {"name": "Bills & Vouchers", "system_kind": "BILLS"},
    {"name": "Operations & Production Runs", "system_kind": "OPERATIONS"},
    {"name": "Payroll & Statutory Challans", "system_kind": "PAYROLL"},
]

MASTER_LIBRARY: dict = {
    "name": "Master Library",
    "system_kind": "MASTER_LIBRARY",
    "children": [
        {"name": "ISO Quality Manual & Approved SOPs", "system_kind": "MASTER_SOP"},
        {"name": "Stock Item Drawings & Engineering Specs", "system_kind": "MASTER_DRAWINGS"},
        {"name": "Calibration & Equipment Certificates", "system_kind": "MASTER_CALIBRATION"},
        {"name": "Internal Report & Document Templates", "system_kind": "MASTER_TEMPLATES"},
    ],
}

# content_schema of the org's system MONTHLY_FOLDER_RULE doc_template (custom rules add "custom": [...])
DEFAULT_MONTHLY_RULE: dict = {"subfolders": MONTHLY_SUBFOLDERS, "custom": []}
