import {
  BookOpen, Building2, ChartColumn, CirclePlay, CreditCard, FileText, Folder, History, House, IdCard, KeyRound,
  Landmark, Layers, LayoutDashboard, Package, PenLine, Receipt, ScanLine, ShieldCheck, Users, Wallet, Workflow, Wrench,
  type LucideIcon,
} from "lucide-react";

/**
 * Tenant navigation (design: Sidebar.dc.html). Paths are relative to `/o/<slug>`.
 * Each item is visible when the user has ≥ READ on ANY of `perms`.
 * W2 (accounts) and W3 (operations, documents) own the routes their items point to and may edit
 * their module's `items` here — keep labels/order aligned with the design.
 */
export interface NavItem {
  key: string;
  label: string;
  href: string;
  icon: LucideIcon;
  perms: string[];
  /** Extra path prefixes that should mark this item active. */
  match?: string[];
}

export interface NavModule {
  key: "accounts" | "operations" | "documents" | "organization";
  label: string;
  icon: LucideIcon;
  /** Accent colour of the module icon (design). */
  color: string;
  href: string;
  /** `enabled_modules` key from /org/context (missing → enabled). */
  moduleFlag?: string;
  items: NavItem[];
}

export const NAV: NavModule[] = [
  {
    key: "accounts", label: "Accounts", icon: Wallet, color: "#C35E49", href: "/accounts", moduleFlag: "accounts",
    items: [
      { key: "gateway", label: "Gateway", href: "/accounts", icon: House, perms: ["accounts.*"] },
      { key: "overview", label: "Overview", href: "/accounts/dashboard", icon: LayoutDashboard, perms: ["accounts.dashboard"] },
      { key: "vouchers", label: "Vouchers", href: "/accounts/vouchers", icon: FileText, perms: ["accounts.vouchers"] },
      { key: "daybook", label: "Day book", href: "/accounts/daybook", icon: BookOpen, perms: ["accounts.reports"] },
      { key: "masters", label: "Masters", href: "/accounts/masters", icon: Layers, perms: ["accounts.ledgers_groups"] },
      { key: "inventory", label: "Inventory", href: "/accounts/inventory", icon: Package, perms: ["accounts.inventory_masters"] },
      { key: "banking", label: "Banking", href: "/accounts/banking", icon: Landmark, perms: ["accounts.banking"] },
      { key: "payroll", label: "Payroll", href: "/accounts/payroll", icon: Users, perms: ["accounts.payroll_runs", "accounts.payroll_employees"] },
      { key: "taxation", label: "Taxation", href: "/accounts/taxation", icon: Receipt, perms: ["accounts.taxation"] },
      { key: "reports", label: "Reports", href: "/accounts/reports", icon: ChartColumn, perms: ["accounts.reports"] },
      { key: "utilities", label: "Utilities", href: "/accounts/utilities", icon: Wrench, perms: ["accounts.reports"], match: ["/accounts/settings"] },
    ],
  },
  {
    key: "operations", label: "Operations", icon: Workflow, color: "#4F46E5", href: "/operations", moduleFlag: "operations",
    items: [
      { key: "overview", label: "Overview", href: "/operations", icon: LayoutDashboard, perms: ["operations.dashboard"] },
      { key: "items", label: "Items & processes", href: "/operations/items", icon: Package, perms: ["operations.items"] },
      { key: "workflows", label: "Workflow studio", href: "/operations/workflows", icon: Workflow, perms: ["operations.workflows"] },
      { key: "runs", label: "Period runs", href: "/operations/runs", icon: CirclePlay, perms: ["operations.runs_execution"] },
      { key: "iso", label: "ISO compliance", href: "/operations/iso-compliance", icon: ShieldCheck, perms: ["operations.iso_compliance"] },
    ],
  },
  {
    key: "documents", label: "Documents", icon: Folder, color: "#0BA5EC", href: "/documents", moduleFlag: "documents",
    items: [
      { key: "explorer", label: "Explorer", href: "/documents", icon: Folder, perms: ["documents.explorer"] },
      { key: "editor", label: "Inspection reports", href: "/documents/editor", icon: PenLine, perms: ["documents.editor"], match: ["/documents/reports"] },
      { key: "scan", label: "Scanner", href: "/documents/scan", icon: ScanLine, perms: ["documents.capture_upload"] },
      { key: "templates", label: "Templates", href: "/documents/templates", icon: Layers, perms: ["documents.templates"] },
    ],
  },
  {
    key: "organization", label: "Organization", icon: Building2, color: "#7A5AF8", href: "/organization/profile",
    items: [
      { key: "profile", label: "Profile & branches", href: "/organization/profile", icon: IdCard, perms: ["organization.profile"] },
      { key: "members", label: "Members", href: "/organization/members", icon: Users, perms: ["organization.members"] },
      { key: "roles", label: "Roles & access", href: "/organization/roles", icon: KeyRound, perms: ["organization.roles_rbac"], match: ["/organization/acl"] },
      { key: "security", label: "Security & approvals", href: "/organization/security", icon: ShieldCheck, perms: ["organization.security_policies"] },
      { key: "audit", label: "Audit log", href: "/organization/audit-logs", icon: History, perms: ["organization.audit_logs"] },
      { key: "billing", label: "Billing", href: "/organization/billing", icon: CreditCard, perms: ["organization.billing"] },
    ],
  },
];

export const PERSONAL_NAV: { key: string; label: string; href: string; icon: LucideIcon }[] = [
  { key: "home", label: "Home", href: "/me", icon: House },
  { key: "orgs", label: "My organizations", href: "/me/organizations", icon: Building2 },
  { key: "security", label: "Profile & security", href: "/me/security", icon: KeyRound },
  { key: "create", label: "Create organization", href: "/organizations/new", icon: Layers },
];

/** Longest-prefix match of the current tenant sub-path against nav items. */
export function activeNav(subPath: string): { module: NavModule["key"] | null; item: string | null } {
  let best: { module: NavModule["key"]; item: string; len: number } | null = null;
  for (const m of NAV) {
    for (const it of m.items) {
      for (const p of [it.href, ...(it.match ?? [])]) {
        const hit = subPath === p || subPath.startsWith(`${p}/`);
        if (hit && (!best || p.length > best.len)) best = { module: m.key, item: it.key, len: p.length };
      }
    }
    if (!best && (subPath === m.href || subPath.startsWith(`${m.href}/`))) best = { module: m.key, item: "", len: m.href.length };
  }
  return best ? { module: best.module, item: best.item || null } : { module: null, item: null };
}
