"""Default ledgers created for every new org. ``system_code`` is unique per org and is how other modules
find them (``accounts.interface.get_ledger_ids_by_code``). ``{SGST}`` is replaced by ``UTGST`` for union
territories without a legislature (see ``states.UT_WITHOUT_LEGISLATURE``)."""

DEFAULT_LEDGERS: list[dict] = [
    {"system_code": "CASH", "name": "Cash", "group": "CASH_IN_HAND"},
    {"system_code": "SALES", "name": "Sales", "group": "SALES_ACCOUNTS"},
    {"system_code": "PURCHASE", "name": "Purchase", "group": "PURCHASE_ACCOUNTS"},
    {
        "system_code": "CGST_OUT",
        "name": "Output CGST",
        "group": "DUTIES_TAXES",
        "tax_config": {"tax_type": "GST", "gst_head": "CGST"},
    },
    {
        "system_code": "SGST_OUT",
        "name": "Output {SGST}",
        "group": "DUTIES_TAXES",
        "tax_config": {"tax_type": "GST", "gst_head": "SGST"},
    },
    {
        "system_code": "IGST_OUT",
        "name": "Output IGST",
        "group": "DUTIES_TAXES",
        "tax_config": {"tax_type": "GST", "gst_head": "IGST"},
    },
    {
        "system_code": "CGST_IN",
        "name": "Input CGST",
        "group": "DUTIES_TAXES",
        "tax_config": {"tax_type": "GST", "gst_head": "CGST"},
    },
    {
        "system_code": "SGST_IN",
        "name": "Input {SGST}",
        "group": "DUTIES_TAXES",
        "tax_config": {"tax_type": "GST", "gst_head": "SGST"},
    },
    {
        "system_code": "IGST_IN",
        "name": "Input IGST",
        "group": "DUTIES_TAXES",
        "tax_config": {"tax_type": "GST", "gst_head": "IGST"},
    },
    {
        "system_code": "RCM_PAYABLE",
        "name": "GST Payable on Reverse Charge",
        "group": "DUTIES_TAXES",
        "tax_config": {"tax_type": "GST", "gst_head": "RCM"},
    },
    {"system_code": "ROUND_OFF", "name": "Round Off", "group": "INDIRECT_EXPENSES"},
    {"system_code": "TDS_PAYABLE", "name": "TDS Payable", "group": "DUTIES_TAXES", "tax_config": {"tax_type": "TDS"}},
    {"system_code": "TCS_PAYABLE", "name": "TCS Payable", "group": "DUTIES_TAXES", "tax_config": {"tax_type": "TCS"}},
    {"system_code": "SALARY_PAYABLE", "name": "Salary Payable", "group": "CURRENT_LIABILITIES"},
    {"system_code": "DIRECT_WAGES", "name": "Direct Wages (Production)", "group": "DIRECT_EXPENSES"},
    {"system_code": "ADMIN_SALARIES", "name": "Salaries - Administration", "group": "INDIRECT_EXPENSES"},
    {"system_code": "EMPLOYER_PF_ESIC", "name": "Employer PF & ESIC Contribution", "group": "INDIRECT_EXPENSES"},
    {"system_code": "EPF_PAYABLE", "name": "EPF Payable", "group": "DUTIES_TAXES"},
    {"system_code": "ESIC_PAYABLE", "name": "ESIC Payable", "group": "DUTIES_TAXES"},
    {"system_code": "PT_PAYABLE", "name": "Professional Tax Payable", "group": "DUTIES_TAXES"},
    {
        "system_code": "SALARY_TDS_PAYABLE",
        "name": "TDS on Salary Payable (Sec 192)",
        "group": "DUTIES_TAXES",
        "tax_config": {"tax_type": "TDS", "tds_section": "192"},
    },
    {"system_code": "SCRAP_RECOVERY", "name": "Scrap Sales / Recovery", "group": "DIRECT_INCOMES"},
    {"system_code": "MFG_OVERHEAD", "name": "Manufacturing Overheads", "group": "DIRECT_EXPENSES"},
    {"system_code": "STOCK_FG", "name": "Finished Goods Stock", "group": "STOCK_IN_HAND"},
    {"system_code": "STOCK_RM", "name": "Raw Material Stock", "group": "STOCK_IN_HAND"},
    {"system_code": "STOCK_WIP", "name": "Work-in-Progress Stock", "group": "STOCK_IN_HAND"},
    {"system_code": "STOCK_SCRAP", "name": "Scrap Stock", "group": "STOCK_IN_HAND"},
    {"system_code": "FOREX_GAIN_LOSS", "name": "Forex Gain / Loss", "group": "INDIRECT_EXPENSES"},
]

# System godowns (accounts.interface.get_system_godown_ids keys)
SYSTEM_GODOWNS: list[dict] = [
    {"system_code": "MAIN", "name": "Main Location", "godown_type": "INTERNAL"},
    {"system_code": "WIP", "name": "Work-in-Progress", "godown_type": "WIP"},
    {"system_code": "SCRAP", "name": "Scrap Yard", "godown_type": "SCRAP"},
    {"system_code": "FG", "name": "Finished Goods Store", "godown_type": "FG"},
]

# Extra ledgers by industry keyword (matched case-insensitively against organizations.industry_type)
INDUSTRY_LEDGERS: dict[str, list[dict]] = {
    "manufactur": [
        {"system_code": None, "name": "Power & Fuel", "group": "DIRECT_EXPENSES"},
        {"system_code": None, "name": "Freight Inward", "group": "DIRECT_EXPENSES"},
        {"system_code": None, "name": "Job Work Charges", "group": "DIRECT_EXPENSES"},
        {"system_code": None, "name": "Consumables & Tools", "group": "DIRECT_EXPENSES"},
    ],
    "engineering": [
        {"system_code": None, "name": "Power & Fuel", "group": "DIRECT_EXPENSES"},
        {"system_code": None, "name": "Job Work Charges", "group": "DIRECT_EXPENSES"},
    ],
    "service": [{"system_code": None, "name": "Service Income", "group": "DIRECT_INCOMES"}],
}
