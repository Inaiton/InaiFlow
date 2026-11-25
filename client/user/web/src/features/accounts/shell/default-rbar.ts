import { kindOf } from "../lib/voucher-kinds";
import type { RBarItem } from "./rbar-context";

const v = (base: string, href: (p: string) => string, active?: string): RBarItem => {
  const k = kindOf(base)!;
  return { id: `v-${base}`, combo: k.combo ?? undefined, label: k.label, href: href(`/vouchers/new?type=${base}`), active: active === base };
};

/** Default right bar (design RBar set "default"). */
export function defaultRBar(href: (p: string) => string): RBarItem[] {
  return [
    v("CONTRA", href), v("PAYMENT", href), v("RECEIPT", href), v("JOURNAL", href), v("SALES", href), v("PURCHASE", href),
    { id: "daybook", combo: "alt+d", label: "Day book", href: href("/daybook"), sep: true },
    { id: "reports", combo: "alt+r", label: "Reports", href: href("/reports") },
    { id: "goto", combo: "alt+g", label: "Go To", noShortcut: true, sep: true },
    { id: "configure", combo: "f12", label: "Configure", href: href("/settings") },
  ];
}

/** Voucher shortcuts for list/report screens that also want the voucher keys. */
export function voucherKeys(href: (p: string) => string, active?: string): RBarItem[] {
  return ["CONTRA", "PAYMENT", "RECEIPT", "JOURNAL", "SALES", "PURCHASE", "DEBIT_NOTE", "CREDIT_NOTE", "STOCK_JOURNAL", "MFG_JOURNAL", "SALES_ORDER", "PURCHASE_ORDER"].map((b) => v(b, href, active));
}
