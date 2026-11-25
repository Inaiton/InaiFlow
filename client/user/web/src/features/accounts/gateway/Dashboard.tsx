"use client";

import { AlertTriangle, ArrowDownRight, ArrowUpRight, BellRing, Landmark, Receipt, Scale, Wallet } from "lucide-react";
import Link from "next/link";
import { Badge, Card, EmptyState, KpiCard, KpiGrid, PageHeader, type Tone } from "@/components/ui";
import { isNegative } from "@/core/money";
import { useOrg } from "@/core/org/OrgProvider";
import { QueryState } from "../components/QueryState";
import { useAccHref } from "../lib/api-base";
import { inr } from "../lib/format";
import { useDashboard } from "../reports/api";
import { CashFlowChart } from "./CashFlowChart";
import { VoucherTable } from "./RecentVouchers";

const ICONS = [Landmark, ArrowDownRight, ArrowUpRight, Scale, Receipt, Wallet];
const TONES: Tone[] = ["teal", "indigo", "orange", "violet", "sky", "accent"];
const sev = (s: string): Tone => (s === "HIGH" || s === "ERROR" || s === "CRITICAL" ? "danger" : s === "WARNING" || s === "MEDIUM" ? "warning" : "sky");

/** /accounts/dashboard — KPIs, cash-flow chart, compliance alerts, recent vouchers. */
export function Dashboard() {
  const href = useAccHref();
  const { slug } = useOrg();
  const q = useDashboard();
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Overview" }]} title="Financial overview" description="Live from posted vouchers · cancelled, optional and memorandum vouchers excluded" />
      <QueryState q={q} rows={6}>
        {(d) => (
          <>
            <KpiGrid>
              {d.kpis.map((k, i) => (
                <KpiCard key={k.key} title={k.label} value={inr(k.value, 0)} icon={ICONS[i % ICONS.length]!} tone={TONES[i % TONES.length]}
                  change={k.change_pct ? { label: `${isNegative(k.change_pct) ? "" : "+"}${k.change_pct}%`, tone: isNegative(k.change_pct) ? "danger" : "success" } : undefined} />
              ))}
            </KpiGrid>
            <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
              <Card title="Cash flow" description="Bank & cash inflow vs outflow by month"><CashFlowChart points={d.cash_flow} /></Card>
              <Card title="Alerts" description="Compliance, credit and stock">
                {d.alerts.length === 0 ? <EmptyState icon={BellRing} tone="success" title="All clear" /> : (
                  <ul className="flex flex-col gap-2">
                    {d.alerts.map((a, i) => (
                      <li key={i} className="flex items-start gap-2 text-[12.5px]">
                        <AlertTriangle className="mt-0.5 size-4 flex-none text-warning" aria-hidden />
                        <span className="flex-1">{a.link ? <Link href={a.link.startsWith("/") ? `/o/${slug}${a.link}` : a.link}>{a.message}</Link> : a.message}</span>
                        <Badge tone={sev(a.severity)}>{a.kind.replace(/_/g, " ").toLowerCase()}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
            <Card title="Recent vouchers" actions={<Link href={href("/daybook")} className="text-[12.5px]">Day book</Link>} padded={false}>
              <VoucherTable data={d.recent_vouchers} />
            </Card>
          </>
        )}
      </QueryState>
    </>
  );
}
