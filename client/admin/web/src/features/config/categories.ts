export type ConfigTab = "tax" | "seeds" | "iso" | "docs" | "roles" | "flags" | "other";

export interface CategoryMeta {
  label: string;
  tab: ConfigTab;
  /** Statutory rules: change takes effect from an effective-from date. */
  statutory?: boolean;
  /** Master templates that seed new orgs and can be pushed to existing ones. */
  pushable?: boolean;
}

export const TABS: { id: ConfigTab; label: string; description: string }[] = [
  { id: "tax", label: "Tax rules", description: "Statutory rates go live for all organizations from the effective date; past vouchers keep old rates." },
  { id: "seeds", label: "Accounting seeds", description: "Chart of accounts, ledgers, voucher types, units and states seeded into new organizations." },
  { id: "iso", label: "ISO workflows", description: "ISO 9001 process templates available in every organization's workflow library." },
  { id: "docs", label: "Document templates", description: "Report templates and monthly folder blueprints." },
  { id: "roles", label: "Role blueprints", description: "Default RBAC role matrices seeded into new organizations." },
  { id: "flags", label: "Feature flags", description: "Platform-wide switches." },
  { id: "other", label: "Other", description: "Categories without a dedicated editor." },
];

export const CATEGORIES: Record<string, CategoryMeta> = {
  GST_SLABS: { label: "GST rate slabs & cess", tab: "tax", statutory: true },
  TDS_SECTIONS: { label: "TDS / TCS sections", tab: "tax", statutory: true },
  PAYROLL_STATUTORY: { label: "Payroll statutory", tab: "tax", statutory: true },
  PT_SLABS: { label: "Professional tax slabs", tab: "tax", statutory: true },
  INCOME_TAX_SLABS: { label: "Income-tax slabs", tab: "tax", statutory: true },
  HSN_SAC: { label: "HSN / SAC codes", tab: "tax", statutory: true },
  EWAY_THRESHOLDS: { label: "e-Way bill thresholds", tab: "tax", statutory: true },
  ACCOUNT_GROUPS: { label: "Account groups", tab: "seeds", pushable: true },
  DEFAULT_LEDGERS: { label: "Default ledgers", tab: "seeds", pushable: true },
  VOUCHER_TYPES: { label: "Voucher types", tab: "seeds", pushable: true },
  UOM: { label: "Units of measure", tab: "seeds", pushable: true },
  INDIAN_STATES: { label: "States & GST codes", tab: "seeds" },
  STATES: { label: "States & GST codes", tab: "seeds" },
  ISO_WORKFLOW_TEMPLATES: { label: "ISO workflow templates", tab: "iso", pushable: true },
  ISO_CHECKLIST: { label: "ISO 9001 checklist", tab: "iso", pushable: true },
  DOC_REPORT_TEMPLATES: { label: "Report templates", tab: "docs", pushable: true },
  FOLDER_TEMPLATES: { label: "Folder templates", tab: "docs", pushable: true },
  DEFAULT_ROLES: { label: "Default roles", tab: "roles", pushable: true },
  FEATURE_FLAGS: { label: "Feature flags", tab: "flags" },
};

export function categoryMeta(category: string): CategoryMeta {
  return CATEGORIES[category] ?? { label: category.replace(/_/g, " ").toLowerCase(), tab: "other" };
}
