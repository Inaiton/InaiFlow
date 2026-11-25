"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAccHref } from "../lib/api-base";

/** Tab-style links between sibling screens (masters, inventory, taxation, payroll…). */
export function SubNav({ items }: { items: { label: string; path: string; exact?: boolean }[] }) {
  const href = useAccHref();
  const pathname = usePathname();
  return (
    <nav aria-label="Section" className="flex flex-wrap gap-1 border-b border-line">
      {items.map((i) => {
        const h = href(i.path);
        const on = i.exact ? pathname === h : pathname === h || pathname.startsWith(`${h}/`);
        return (
          <Link key={i.path} href={h} aria-current={on ? "page" : undefined}
            className={cn("-mb-px border-b-2 px-3 py-2 text-[13px] font-medium no-underline", on ? "border-primary text-primary-text" : "border-transparent text-fg-3 hover:text-fg")}>
            {i.label}
          </Link>
        );
      })}
    </nav>
  );
}

export const MASTERS_NAV = [
  { label: "Groups", path: "/masters/groups" },
  { label: "Ledgers", path: "/masters/ledgers" },
  { label: "Cost centres & budgets", path: "/masters/cost-centres" },
  { label: "Voucher types", path: "/masters/voucher-types" },
  { label: "Currencies", path: "/masters/currencies" },
];
export const INVENTORY_NAV = [
  { label: "Stock summary", path: "/inventory", exact: true },
  { label: "Stock items", path: "/inventory/items" },
  { label: "Stock groups", path: "/inventory/groups" },
  { label: "Godowns", path: "/inventory/godowns" },
];
export const TAX_NAV = [
  { label: "GST summary", path: "/taxation", exact: true },
  { label: "GSTR-1", path: "/taxation/gstr1" },
  { label: "GSTR-3B", path: "/taxation/gstr3b" },
  { label: "GSTR-2B reconciliation", path: "/taxation/gstr2b" },
  { label: "Validator", path: "/taxation/validate" },
  { label: "TDS / TCS", path: "/taxation/tds" },
];
export const PAYROLL_NAV = [
  { label: "Pay runs", path: "/payroll", exact: true },
  { label: "Employees", path: "/payroll/employees" },
  { label: "Attendance", path: "/payroll/attendance" },
  { label: "Settings", path: "/payroll/settings" },
];
export const BANKING_NAV = [
  { label: "Bank accounts", path: "/banking", exact: true },
  { label: "Cheques", path: "/banking/cheques" },
];
