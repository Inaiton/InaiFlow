import { Building2, CreditCard, Gauge, Layers, ScrollText, Settings2, ShieldCheck, Users, Activity, type LucideIcon } from "lucide-react";
import type { AdminAction } from "@/core/permissions/admin-can";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  action: AdminAction;
}

export const NAV: NavItem[] = [
  { href: "/", label: "Command dashboard", icon: Gauge, action: "GET /admin/dashboard" },
  { href: "/organizations", label: "Organizations", icon: Building2, action: "GET /admin/organizations" },
  { href: "/users", label: "Global users", icon: Users, action: "GET /admin/users" },
  { href: "/config", label: "Global config", icon: Settings2, action: "GET /admin/configs" },
  { href: "/plans", label: "Plans", icon: Layers, action: "GET /admin/plans" },
  { href: "/billing", label: "Billing", icon: CreditCard, action: "GET /admin/billing/invoices" },
  { href: "/audit-logs", label: "Platform audit", icon: ScrollText, action: "GET /admin/audit-logs" },
  { href: "/admins", label: "Admins", icon: ShieldCheck, action: "GET /admin/admins" },
  { href: "/system", label: "System", icon: Activity, action: "GET /admin/system/health" },
];

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
