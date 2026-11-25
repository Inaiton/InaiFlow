"use client";

import { CirclePlay, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Button, Card, DataTable, DatePicker, EmptyState, ErrorState, Input, NativeSelect, PageHeader, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { formatMoney, formatQty } from "@/core/money";
import { Can } from "@/core/permissions/Can";
import { useRuns, type RunStatus } from "../../api/runs";
import { useOpsPath } from "../../paths";
import { Progress } from "../shared/Progress";
import { RUN_LABEL, RunStatusBadge, periodLabel } from "../shared/status";

type Run = Schemas["RunSummary"];
const LIMIT = 25;

/** /operations/runs — period runs with filters & progress (design Ops-Runs). */
export function RunsPage() {
  const p = useOpsPath();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<RunStatus | "">("");
  const [month, setMonth] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const runs = useRuns({ q: q || undefined, status: status || undefined, period_month: month ?? undefined, limit: LIMIT, offset });
  const cols = useMemo<ColumnDef<Run, unknown>[]>(() => [
    { header: "Run", accessorKey: "run_title", cell: ({ row }) => (
      <span className="flex flex-col"><span className="font-semibold text-fg">{row.original.run_title}</span>
        <span className="text-xs text-fg-muted">{row.original.workflow_name} v{row.original.workflow_version} · {periodLabel(row.original.period_month)}</span></span>
    ) },
    { header: "Status", cell: ({ row }) => <RunStatusBadge status={row.original.status} /> },
    { header: "Now at", cell: ({ row }) => <span className="text-xs">{row.original.current_step_names.join(", ") || "—"}</span> },
    { header: "Progress", cell: ({ row }) => <Progress className="w-32" value={Number(row.original.progress_pct)} /> },
    { header: "Accepted / rejected", cell: ({ row }) => `${formatQty(row.original.accepted_qty)} / ${formatQty(row.original.rejected_qty)} of ${formatQty(row.original.planned_qty)}`, meta: { align: "right" } },
    { header: "Unit cost", cell: ({ row }) => formatMoney(row.original.computed_unit_cost), meta: { align: "right" } },
  ], []);
  const launch = <Can permission="operations.runs_execution" level="WRITE"><Button asChild variant="primary"><Link href={p("/runs/new")}><CirclePlay /> Launch run</Link></Button></Can>;
  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Operations", href: p() }, { label: "Period runs" }]} title="Period runs" description="One workflow executed for one month" actions={launch} />
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <Input className="max-w-xs" prefix={<Search className="size-4" />} placeholder="Search runs" value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} aria-label="Search runs" />
          <NativeSelect className="w-44" aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value as RunStatus | ""); setOffset(0); }}>
            <option value="">All statuses</option>
            {Object.entries(RUN_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </NativeSelect>
          <DatePicker className="w-44" mode="month" aria-label="Period" value={month} onValueChange={(v) => { setMonth(v); setOffset(0); }} />
          {month ? <Button size="sm" variant="ghost" onClick={() => setMonth(null)}>Any month</Button> : null}
        </div>
        {runs.isError ? <ErrorState message={describeError(runs.error)} onRetry={() => void runs.refetch()} /> : (
          <DataTable aria-label="Runs" columns={cols} data={runs.data?.items} loading={runs.isPending} getRowId={(r) => r.id}
            onRowClick={(r) => router.push(p(`/runs/${r.id}`))}
            pagination={runs.data ? { total: runs.data.total, limit: LIMIT, offset, onOffsetChange: setOffset } : undefined}
            empty={<EmptyState icon={CirclePlay} tone="indigo" title="No runs here" description="Launch a run from a published workflow." action={launch} />} />
        )}
      </Card>
    </div>
  );
}
