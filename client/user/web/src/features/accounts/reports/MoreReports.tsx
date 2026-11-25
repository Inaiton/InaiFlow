"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Card, DataTable, EmptyState, Field, IconTile, Input, PageHeader, Segmented, StatusBadge, type ColumnDef } from "@/components/ui";
import { BookOpen, ChartColumn, Clock, Factory, Landmark, Package, Scale, TrendingUp, Wallet, type LucideIcon } from "lucide-react";
import type { Schemas } from "@/core/api/types";
import { monthLabel } from "@/core/dates";
import { Amt } from "../components/Amount";
import { QueryState } from "../components/QueryState";
import { useAccHref } from "../lib/api-base";
import { useDebouncedValue } from "../lib/hooks";
import { periodQuery, usePeriod } from "../lib/use-period";
import { qty } from "../lib/format";
import { useAgeing, useBatchCosting } from "./api";
import { ReportFrame } from "./ReportFrame";

type Ageing = Schemas["AgeingRow"];
type Batch = Schemas["BatchCostRow"];

/** /accounts/reports/ageing — receivables / payables by overdue bucket with MSME 45-day flag (design: Acc-Rep-Outstanding). */
export function AgeingPage() {
  const p = usePeriod();
  const href = useAccHref();
  const [kind, setKind] = useState<"RECEIVABLE" | "PAYABLE">("RECEIVABLE");
  const [bucketText, setBucketText] = useState("30,60,90");
  const buckets = useDebouncedValue(bucketText, 400);
  const q = useAgeing({ kind, as_of: p.period.to, ...(/^\d+(,\d+)*$/.test(buckets) ? { buckets } : {}) });
  return (
    <ReportFrame title={kind === "RECEIVABLE" ? "Receivables ageing" : "Payables ageing"} report="ageing" {...p} asOf exportQuery={{ as_of: p.period.to, kind }}
      actions={<Segmented value={kind} onChange={setKind} options={[{ value: "RECEIVABLE", label: "Receivables" }, { value: "PAYABLE", label: "Payables" }]} />}>
      <div className="w-56"><Field label="Buckets (days)" hint="e.g. 30,60,90"><Input value={bucketText} onChange={(e) => setBucketText(e.target.value)} /></Field></div>
      <QueryState q={q}>
        {(a) => {
          const cols: ColumnDef<Ageing, unknown>[] = [
            { accessorKey: "party_name", header: "Party", cell: ({ row: { original: r } }) => <span className="flex items-center gap-2"><Link href={href(`/masters/ledgers/${r.ledger_id}?${periodQuery(p.period)}`)}>{r.party_name}</Link>{r.msme_overdue ? <Badge tone="danger">MSME &gt; 45 days</Badge> : null}</span> },
            ...a.bucket_labels.map((b): ColumnDef<Ageing, unknown> => ({ id: b, header: b, meta: { align: "right" }, cell: ({ row: { original: r } }) => <Amt v={r.buckets[b]} blankZero /> })),
            { accessorKey: "total", header: "Total", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} strong /> },
          ];
          return (
            <Card padded={false}>
              <DataTable columns={cols} data={a.rows} getRowId={(r) => r.ledger_id} aria-label="Ageing" empty={<EmptyState title="No outstanding bills" />} />
              <div className="flex flex-wrap justify-end gap-4 border-t-2 border-fg px-4 py-2 text-[13px] font-semibold">{Object.entries(a.totals).map(([k, v]) => <span key={k}>{k}: <Amt v={v} /></span>)}</div>
            </Card>
          );
        }}
      </QueryState>
    </ReportFrame>
  );
}

/** /accounts/reports/batch-costing — period runs: accepted/rejected, Dr/Cr money flow, unit cost. */
export function BatchCostingPage() {
  const p = usePeriod();
  const range = { date_from: p.period.from, date_to: p.period.to };
  const q = useBatchCosting(range);
  const cols: ColumnDef<Batch, unknown>[] = [
    { accessorKey: "run_title", header: "Period run", cell: ({ row: { original: r } }) => <span className="flex flex-col"><span className="font-medium text-fg">{r.run_title}</span><span className="text-[11.5px] text-fg-muted">{r.stock_item_name ?? "—"} · {monthLabel(r.period_month.slice(0, 7))}</span></span> },
    { accessorKey: "status", header: "Status", cell: ({ getValue }) => <StatusBadge status={getValue() as string} /> },
    { id: "qty", header: "Accepted / rejected", meta: { align: "right" }, cell: ({ row: { original: r } }) => <span className="tabular">{qty(r.accepted_qty)} / {qty(r.rejected_qty)}</span> },
    { accessorKey: "total_debit", header: "Debit", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "total_credit", header: "Credit", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "net_cost", header: "Net cost", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "unit_cost", header: "Unit cost", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} strong /> },
  ];
  return (
    <ReportFrame title="Batch costing" report="batch-costing" {...p} exportQuery={range}>
      <Card padded={false}><QueryState q={q}>{(rows) => <DataTable columns={cols} data={rows} getRowId={(r) => r.period_run_id} aria-label="Batch costing" empty={<EmptyState title="No period runs in this period" />} />}</QueryState></Card>
    </ReportFrame>
  );
}

const REPORTS: { label: string; desc: string; path: string; icon: LucideIcon }[] = [
  { label: "Balance sheet", desc: "Schedule-III", path: "/reports/balance-sheet", icon: Scale },
  { label: "Profit & loss A/c", desc: "Trading + P&L, T-format", path: "/reports/profit-loss", icon: TrendingUp },
  { label: "Trial balance", desc: "Group / ledger-wise", path: "/reports/trial-balance", icon: ChartColumn },
  { label: "Cash flow", desc: "Operating, investing, financing", path: "/reports/cash-flow", icon: Wallet },
  { label: "Ratio analysis", desc: "Liquidity, profitability, turnover", path: "/reports/ratios", icon: ChartColumn },
  { label: "Ageing", desc: "Receivables & payables, MSME flag", path: "/reports/ageing", icon: Clock },
  { label: "Day book", desc: "All vouchers by date", path: "/daybook", icon: BookOpen },
  { label: "Ledger statement", desc: "Pick a ledger", path: "/masters/ledgers", icon: Landmark },
  { label: "Stock summary", desc: "Closing stock & value", path: "/inventory", icon: Package },
  { label: "Batch costing", desc: "Period run unit cost", path: "/reports/batch-costing", icon: Factory },
];

/** /accounts/reports — report index. */
export function ReportsHub() {
  const href = useAccHref();
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Reports" }]} title="Reports" description="F2 changes the period on every report · rows drill down to ledgers and vouchers" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {REPORTS.map((r) => <Link key={r.path} href={href(r.path)} className="no-underline"><Card className="h-full hover:border-primary"><div className="flex items-start gap-3"><IconTile icon={r.icon} tone="indigo" /><div><p className="font-semibold text-ink">{r.label}</p><p className="text-[12.5px] text-fg-muted">{r.desc}</p></div></div></Card></Link>)}
      </div>
    </>
  );
}
