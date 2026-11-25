"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, KeyValue, PageHeader, Skeleton } from "@/components/ui";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import { useShortcut } from "@/core/shortcuts/registry";
import { cn } from "@/lib/utils";
import { useAccHref } from "../lib/api-base";
import { accDate, inr } from "../lib/format";
import { periodLabel } from "../lib/period";
import { useAccountsSettings } from "../masters/api";
import { useDashboard } from "../reports/api";

interface Entry { key: string; label: string; path: string; perm: string }

const MENU: { title: string; items: Entry[] }[] = [
  { title: "Masters", items: [
    { key: "c", label: "Create ledger", path: "/masters/ledgers/new", perm: "accounts.ledgers_groups" },
    { key: "a", label: "Alter masters", path: "/masters", perm: "accounts.ledgers_groups" },
    { key: "h", label: "Chart of accounts", path: "/masters/groups", perm: "accounts.ledgers_groups" },
    { key: "l", label: "Ledgers", path: "/masters/ledgers", perm: "accounts.ledgers_groups" },
    { key: "i", label: "Inventory", path: "/inventory", perm: "accounts.inventory_masters" },
  ] },
  { title: "Transactions", items: [
    { key: "v", label: "Vouchers", path: "/vouchers/new?type=SALES", perm: "accounts.vouchers" },
    { key: "d", label: "Day book", path: "/daybook", perm: "accounts.reports" },
    { key: "e", label: "Orders", path: "/vouchers/orders", perm: "accounts.vouchers" },
  ] },
  { title: "Utilities", items: [
    { key: "n", label: "Banking", path: "/banking", perm: "accounts.banking" },
    { key: "y", label: "Payroll", path: "/payroll", perm: "accounts.payroll_runs" },
    { key: "g", label: "GST & statutory", path: "/taxation", perm: "accounts.taxation" },
    { key: "u", label: "Utilities", path: "/utilities", perm: "accounts.reports" },
  ] },
  { title: "Reports", items: [
    { key: "b", label: "Balance sheet", path: "/reports/balance-sheet", perm: "accounts.reports" },
    { key: "p", label: "Profit & loss A/c", path: "/reports/profit-loss", perm: "accounts.reports" },
    { key: "t", label: "Trial balance", path: "/reports/trial-balance", perm: "accounts.reports" },
    { key: "s", label: "Stock summary", path: "/inventory", perm: "accounts.inventory_masters" },
    { key: "r", label: "Ratio analysis", path: "/reports/ratios", perm: "accounts.reports" },
    { key: "m", label: "More reports", path: "/reports", perm: "accounts.reports" },
    { key: "o", label: "Dashboard", path: "/dashboard", perm: "accounts.dashboard" },
  ] },
];

function MenuItem({ e }: { e: Entry }) {
  const href = useAccHref();
  const router = useRouter();
  const allowed = useCan(e.perm, "READ");
  useShortcut(e.key, () => router.push(href(e.path)), { scope: "accounts", enabled: allowed, description: e.label, group: "Gateway" });
  const i = e.label.toLowerCase().indexOf(e.key);
  const label = i >= 0 ? <>{e.label.slice(0, i)}<span className="font-bold text-primary underline underline-offset-2">{e.label[i]}</span>{e.label.slice(i + 1)}</> : e.label;
  return (
    <li>
      <Link href={href(e.path)} aria-disabled={!allowed || undefined}
        className={cn("flex items-center justify-between rounded-md px-3 py-1.5 text-[13.5px] text-fg no-underline hover:bg-primary-tint focus:bg-primary-tint", !allowed && "pointer-events-none opacity-40")}>
        <span>{label}</span><span className="text-[11px] font-bold text-indigo uppercase">{e.key}</span>
      </Link>
    </li>
  );
}

function AtAGlance() {
  const href = useAccHref();
  const canDash = useCan("accounts.dashboard", "READ");
  const dash = useDashboard();
  if (!canDash) return null;
  return (
    <Card title="At a glance" actions={<Link href={href("/dashboard")} className="text-[12.5px]">Open dashboard</Link>}>
      {dash.isPending ? <Skeleton className="h-28 w-full" /> : dash.data ? (
        <KeyValue rows={dash.data.kpis.slice(0, 6).map((k) => [k.label, <span key={k.key} className="font-semibold text-ink tabular">{inr(k.value, 0)}</span>])} />
      ) : <p className="text-[12.5px] text-fg-muted">Dashboard unavailable.</p>}
    </Card>
  );
}

/** /accounts — Gateway of InaiFlow (design: Acc-Gateway): single-key menu, company panel, at-a-glance KPIs. */
export function Gateway() {
  const { context } = useOrg();
  const settings = useAccountsSettings();
  return (
    <>
      <PageHeader title="Gateway of InaiFlow" description="Keyboard-first menu: press the highlighted letter, Enter to open, Esc to go back" />
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <nav aria-label="Gateway menu" className="overflow-hidden rounded-xl border border-line bg-surface">
          <div className="bg-fg px-4 py-2 text-center text-[13px] font-semibold text-white">Gateway of InaiFlow</div>
          <div className="mx-auto flex max-w-md flex-col gap-3 px-4 py-4">
            {MENU.map((s) => (
              <section key={s.title}>
                <h2 className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-fg-muted uppercase">{s.title}</h2>
                <ul className="flex flex-col">{s.items.map((e) => <MenuItem key={e.key} e={e} />)}</ul>
              </section>
            ))}
            <p className="px-3 text-[11.5px] text-fg-muted">Go to anything: Alt G · Create: Alt C · Help: ?</p>
          </div>
        </nav>
        <div className="flex flex-col gap-4">
          <Card title="Company">
            <KeyValue rows={[
              ["Name", context.mailing_name || context.legal_name],
              ["Current period", periodLabel({ from: context.current_fy.start, to: context.current_fy.end })],
              ["Current date", accDate(new Date().toISOString().slice(0, 10))],
              ["Books begin", accDate(context.books_beginning_from)],
              ["Books locked till", settings.data?.books_locked_until ? accDate(settings.data.books_locked_until) : "Not locked"],
            ]} />
          </Card>
          <AtAGlance />
        </div>
      </div>
    </>
  );
}
