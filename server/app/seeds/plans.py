"""Subscription plans seeded by migration 0001 (prices in INR as decimal strings)."""

ALL_MODULES = {"accounts": True, "payroll": True, "operations": True, "documents": True}

PLANS: list[dict] = [
    {"plan_code": "FREE_TRIAL", "name": "Free Trial", "monthly_price_inr": "0", "annual_price_inr": "0",
     "max_internal_seats": 5, "max_external_collaborators": 2, "max_storage_gb": 2,
     "enabled_modules": {**ALL_MODULES, "tally_xml_sync": False, "irp_einvoice": False}},
    {"plan_code": "STARTER", "name": "Starter", "monthly_price_inr": "1999", "annual_price_inr": "19990",
     "max_internal_seats": 10, "max_external_collaborators": 3, "max_storage_gb": 10,
     "enabled_modules": {"accounts": True, "payroll": True, "operations": False, "documents": True,
                         "tally_xml_sync": False, "irp_einvoice": False}},
    {"plan_code": "MANUFACTURING_PRO", "name": "Manufacturing Pro", "monthly_price_inr": "5999",
     "annual_price_inr": "59990", "max_internal_seats": 30, "max_external_collaborators": 10,
     "max_storage_gb": 100, "enabled_modules": {**ALL_MODULES, "tally_xml_sync": True, "irp_einvoice": False}},
    {"plan_code": "ENTERPRISE", "name": "Enterprise", "monthly_price_inr": "14999", "annual_price_inr": "149990",
     "max_internal_seats": 200, "max_external_collaborators": 50, "max_storage_gb": 1000,
     "enabled_modules": {**ALL_MODULES, "tally_xml_sync": True, "irp_einvoice": True}},
]  # fmt: skip

DEFAULT_PLAN_CODE = "FREE_TRIAL"
TRIAL_DAYS = 14

FEATURE_FLAGS: dict = {
    "accounts": True, "payroll": True, "operations": True, "documents": True,
    "tally_xml_sync": True, "irp_einvoice": False, "google_oauth": True,
}  # fmt: skip
