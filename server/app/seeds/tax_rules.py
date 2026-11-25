"""Statutory rules as configuration (07_ACCOUNTING_TAX_PAYROLL_RULES §2-4). All numbers are decimal strings.

Effective from 2025-04-01 (version 1). Superadmin publishes new versions with later effective dates;
business logic reads them through ``platform.interface.get_config(db, category, key, on_date)``.
"""

GST_SLABS: dict = {
    "rates": ["0", "0.25", "3", "5", "12", "18", "28"],
    "cess": {"modes": ["AD_VALOREM_PCT", "SPECIFIC_PER_UNIT"]},
    "eway_bill_threshold": "50000",
    "einvoice_aato_threshold": "50000000",
    "b2cl_threshold": "100000",
    "hsn_digits": {"upto_5cr": 4, "above_5cr": 6},
    "rcm_common": [
        {"service": "Goods Transport Agency (GTA)", "rate": "5"},
        {"service": "Legal services by advocate", "rate": "18"},
        {"service": "Import of services", "rate": "18"},
    ],
}

TDS_SECTIONS: dict = {
    "due_day_of_next_month": 7,
    "march_due_date": "04-30",
    "sections": [
        {"kind": "TDS", "section": "194C", "nature": "Contractors / Sub-contractors / Job Work",
         "threshold_single": "30000", "threshold_annual": "100000",
         "rate_individual": "1", "rate_company": "2", "rate_no_pan": "20"},
        {"kind": "TDS", "section": "194J(a)", "nature": "Technical services / Royalty / Call centre",
         "threshold_single": None, "threshold_annual": "30000",
         "rate_individual": "2", "rate_company": "2", "rate_no_pan": "20"},
        {"kind": "TDS", "section": "194J(b)", "nature": "Professional services",
         "threshold_single": None, "threshold_annual": "30000",
         "rate_individual": "10", "rate_company": "10", "rate_no_pan": "20"},
        {"kind": "TDS", "section": "194I(a)", "nature": "Rent of plant, machinery or equipment",
         "threshold_single": None, "threshold_annual": "240000",
         "rate_individual": "2", "rate_company": "2", "rate_no_pan": "20"},
        {"kind": "TDS", "section": "194I(b)", "nature": "Rent of land, building or furniture",
         "threshold_single": None, "threshold_annual": "240000",
         "rate_individual": "10", "rate_company": "10", "rate_no_pan": "20"},
        {"kind": "TDS", "section": "194H", "nature": "Commission or brokerage",
         "threshold_single": None, "threshold_annual": "15000",
         "rate_individual": "2", "rate_company": "2", "rate_no_pan": "20"},
        {"kind": "TDS", "section": "194Q", "nature": "Purchase of goods (buyer turnover > 10 Cr)",
         "threshold_single": None, "threshold_annual": "5000000", "applies_on_excess": True,
         "rate_individual": "0.1", "rate_company": "0.1", "rate_no_pan": "5"},
        {"kind": "TCS", "section": "206C(1)", "nature": "TCS on scrap sale",
         "threshold_single": None, "threshold_annual": None,
         "rate_individual": "1", "rate_company": "1", "rate_no_pan": "5"},
        {"kind": "TCS", "section": "206C(1H)", "nature": "TCS on sale of goods (if 194Q not applicable)",
         "threshold_single": None, "threshold_annual": "5000000", "applies_on_excess": True,
         "rate_individual": "0.1", "rate_company": "0.1", "rate_no_pan": "1"},
    ],
}  # fmt: skip

EPF: dict = {
    "wage_ceiling": "15000",
    "employee_rate": "12",
    "employer_eps_rate": "8.33",
    "employer_eps_cap": "1250",
    "employer_epf_rate": "3.67",
    "edli_rate": "0.5",
    "edli_cap": "75",
    "admin_charges_rate": "0.5",
    "admin_charges_min": "500",
    "wage_components": ["basic", "da"],
    "mandatory_employee_count": 20,
}

ESIC: dict = {
    "gross_ceiling": "21000",
    "gross_ceiling_disabled": "25000",
    "employee_rate": "0.75",
    "employer_rate": "3.25",
    "employee_rounding": "CEIL_RUPEE",
}

# Monthly-gross based slabs. frequency HALF_YEARLY: slabs are on half-yearly income and the amount is
# deducted in the listed months; MONTHLY: amount deducted every month (feb_amount overrides February).
PT_SLABS: dict = {
    "states": {
        "33": {"name": "Tamil Nadu", "frequency": "HALF_YEARLY", "deduction_months": [9, 3], "slabs": [
            {"min": "0", "max": "21000", "amount": "0"},
            {"min": "21000.01", "max": "30000", "amount": "180"},
            {"min": "30000.01", "max": "45000", "amount": "425"},
            {"min": "45000.01", "max": "60000", "amount": "930"},
            {"min": "60000.01", "max": "75000", "amount": "1025"},
            {"min": "75000.01", "max": None, "amount": "1250"}]},
        "27": {"name": "Maharashtra", "frequency": "MONTHLY", "slabs": [
            {"min": "0", "max": "7500", "amount": "0"},
            {"min": "7500.01", "max": "10000", "amount": "175"},
            {"min": "10000.01", "max": None, "amount": "200", "feb_amount": "300"}],
            "notes": "Women earning up to 25000/month are exempt."},
        "29": {"name": "Karnataka", "frequency": "MONTHLY", "slabs": [
            {"min": "0", "max": "14999.99", "amount": "0"},
            {"min": "15000", "max": None, "amount": "200"}]},
        "32": {"name": "Kerala", "frequency": "HALF_YEARLY", "deduction_months": [9, 3], "slabs": [
            {"min": "0", "max": "11999.99", "amount": "0"},
            {"min": "12000", "max": "17999.99", "amount": "120"},
            {"min": "18000", "max": "29999.99", "amount": "180"},
            {"min": "30000", "max": "44999.99", "amount": "300"},
            {"min": "45000", "max": "59999.99", "amount": "450"},
            {"min": "60000", "max": "74999.99", "amount": "600"},
            {"min": "75000", "max": "99999.99", "amount": "750"},
            {"min": "100000", "max": "124999.99", "amount": "1000"},
            {"min": "125000", "max": None, "amount": "1250"}]},
        "37": {"name": "Andhra Pradesh", "frequency": "MONTHLY", "slabs": [
            {"min": "0", "max": "15000", "amount": "0"},
            {"min": "15000.01", "max": "20000", "amount": "150"},
            {"min": "20000.01", "max": None, "amount": "200"}]},
        "36": {"name": "Telangana", "frequency": "MONTHLY", "slabs": [
            {"min": "0", "max": "15000", "amount": "0"},
            {"min": "15000.01", "max": "20000", "amount": "150"},
            {"min": "20000.01", "max": None, "amount": "200"}]},
        "19": {"name": "West Bengal", "frequency": "MONTHLY", "slabs": [
            {"min": "0", "max": "10000", "amount": "0"},
            {"min": "10000.01", "max": "15000", "amount": "110"},
            {"min": "15000.01", "max": "25000", "amount": "130"},
            {"min": "25000.01", "max": "40000", "amount": "150"},
            {"min": "40000.01", "max": None, "amount": "200"}]},
        "24": {"name": "Gujarat", "frequency": "MONTHLY", "slabs": [
            {"min": "0", "max": "11999.99", "amount": "0"},
            {"min": "12000", "max": None, "amount": "200"}]},
    }
}  # fmt: skip

INCOME_TAX: dict = {
    "fy": "2025-26",
    "cess_rate": "4",
    "regimes": {
        "NEW": {
            "standard_deduction": "75000",
            "slabs": [
                {"from": "0", "to": "400000", "rate": "0"},
                {"from": "400000", "to": "800000", "rate": "5"},
                {"from": "800000", "to": "1200000", "rate": "10"},
                {"from": "1200000", "to": "1600000", "rate": "15"},
                {"from": "1600000", "to": "2000000", "rate": "20"},
                {"from": "2000000", "to": "2400000", "rate": "25"},
                {"from": "2400000", "to": None, "rate": "30"}],
            "rebate_87a": {"income_limit": "1200000", "max_rebate": "60000", "marginal_relief": True},
            "surcharge": [{"above": "5000000", "rate": "10"}, {"above": "10000000", "rate": "15"},
                          {"above": "20000000", "rate": "25"}],
        },
        "OLD": {
            "standard_deduction": "50000",
            "slabs": [
                {"from": "0", "to": "250000", "rate": "0"},
                {"from": "250000", "to": "500000", "rate": "5"},
                {"from": "500000", "to": "1000000", "rate": "20"},
                {"from": "1000000", "to": None, "rate": "30"}],
            "rebate_87a": {"income_limit": "500000", "max_rebate": "12500", "marginal_relief": False},
            "surcharge": [{"above": "5000000", "rate": "10"}, {"above": "10000000", "rate": "15"},
                          {"above": "20000000", "rate": "25"}, {"above": "50000000", "rate": "37"}],
            "deductions_allowed": ["80C", "80D", "HRA", "24B"],
        },
    },
}  # fmt: skip
