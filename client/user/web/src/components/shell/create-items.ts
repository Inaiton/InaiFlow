import { BookOpen, Camera, FileText, Landmark, Package, PlayCircle, Receipt, Upload, UserPlus, Users, Wallet, Workflow, type LucideIcon } from "lucide-react";
import type { Level } from "@/core/permissions/levels";

/** Alt+C create menu (design: Glb-Create.dc.html). Hrefs are relative to `/o/<slug>`; owned routes per stream. */
export interface CreateItem {
  key: string;
  group: "Vouchers" | "Masters" | "Operations, documents & people";
  label: string;
  hint: string;
  shortcut: string;
  href: string;
  icon: LucideIcon;
  perm: string;
  level: Level;
}

const v = (type: string, label: string, hint: string, shortcut: string, icon: LucideIcon): CreateItem => ({
  key: `voucher-${type}`, group: "Vouchers", label, hint, shortcut, icon,
  href: `/accounts/vouchers/new?type=${type}`, perm: "accounts.vouchers", level: "WRITE",
});

export const CREATE_ITEMS: CreateItem[] = [
  v("SALES", "Sales", "Invoice + GST", "f8", Receipt),
  v("PURCHASE", "Purchase", "Bills + ITC", "f9", FileText),
  v("PAYMENT", "Payment", "Outgoing", "f5", Wallet),
  v("RECEIPT", "Receipt", "Incoming", "f6", Wallet),
  v("JOURNAL", "Journal", "Adjustments", "f7", BookOpen),
  v("CONTRA", "Contra", "Cash / bank", "f4", Landmark),
  { key: "ledger", group: "Masters", label: "Ledger", hint: "Party, bank, expense", shortcut: "l", href: "/accounts/masters/ledgers/new", icon: BookOpen, perm: "accounts.ledgers_groups", level: "WRITE" },
  { key: "stock-item", group: "Masters", label: "Stock item", hint: "With HSN & GST", shortcut: "i", href: "/accounts/inventory/items/new", icon: Package, perm: "accounts.inventory_masters", level: "WRITE" },
  { key: "employee", group: "Masters", label: "Employee", hint: "Payroll master", shortcut: "e", href: "/accounts/payroll/employees/new", icon: Users, perm: "accounts.payroll_employees", level: "WRITE" },
  { key: "run", group: "Operations, documents & people", label: "Period run", hint: "Launch a workflow", shortcut: "r", href: "/operations/runs/new", icon: PlayCircle, perm: "operations.runs_execution", level: "WRITE" },
  { key: "workflow", group: "Operations, documents & people", label: "Workflow", hint: "Flowchart studio", shortcut: "w", href: "/operations/workflows/new", icon: Workflow, perm: "operations.workflows", level: "WRITE" },
  { key: "upload", group: "Operations, documents & people", label: "Upload documents", hint: "Into a folder", shortcut: "u", href: "/documents?upload=1", icon: Upload, perm: "documents.capture_upload", level: "WRITE" },
  { key: "scan", group: "Operations, documents & people", label: "Scan", hint: "Camera scanner", shortcut: "s", href: "/documents/scan", icon: Camera, perm: "documents.capture_upload", level: "WRITE" },
  { key: "report", group: "Operations, documents & people", label: "Inspection report", hint: "Template + run, auto-filled", shortcut: "q", href: "/documents/reports/new", icon: FileText, perm: "documents.editor", level: "WRITE" },
  { key: "invite", group: "Operations, documents & people", label: "Invite member", hint: "Email + role", shortcut: "m", href: "/organization/members?invite=1", icon: UserPlus, perm: "organization.members", level: "FULL" },
];
