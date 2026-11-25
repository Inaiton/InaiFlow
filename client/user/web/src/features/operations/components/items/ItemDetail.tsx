"use client";

import { CirclePlay, ExternalLink, Pencil, Workflow } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Badge, Button, Card, DataTable, EmptyState, ErrorState, KeyValue, KpiCard, KpiGrid, PageHeader, Skeleton, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { formatDate } from "@/core/dates";
import { formatMoney, formatQty } from "@/core/money";
import { Can } from "@/core/permissions/Can";
import { useItemRuns, useOpsItem } from "../../api/items";
import { useWorkflows } from "../../api/workflows";
import { useOpsPath } from "../../paths";
import { RunStatusBadge, periodLabel } from "../shared/status";
import { readFields } from "./item-fields";

type Run = Schemas["RunSummary"];

const runCols: ColumnDef<Run, unknown>[] = [
  { header: "Period", cell: ({ row }) => periodLabel(row.original.period_month) },
  { header: "Run", accessorKey: "run_title" },
  { header: "Status", cell: ({ row }) => <RunStatusBadge status={row.original.status} /> },
  { header: "Accepted", cell: ({ row }) => `${formatQty(row.original.accepted_qty)} of ${formatQty(row.original.planned_qty)}`, meta: { align: "right" } },
  { header: "Yield", cell: ({ row }) => (row.original.yield_pct ? `${formatQty(row.original.yield_pct, 1)}%` : "—"), meta: { align: "right" } },
  { header: "Unit cost", cell: ({ row }) => formatMoney(row.original.computed_unit_cost), meta: { align: "right" } },
];

export function ItemDetail({ itemId }: { itemId: string }) {
  const p = useOpsPath();
  const router = useRouter();
  const item = useOpsItem(itemId);
  const runs = useItemRuns(itemId);
  const workflows = useWorkflows({ stock_item_id: itemId });
  if (item.isError) return <ErrorState message={describeError(item.error)} onRetry={() => void item.refetch()} />;
  if (!item.data) return <Skeleton className="h-96" />;
  const it = item.data;
  const { values, defs } = readFields(it.custom_fields);
  const s = it.stats;
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        crumbs={[{ label: "Operations", href: p() }, { label: "Items", href: p("/items") }, { label: it.name }]}
        title={it.name}
        description={it.target_type === "STANDALONE_PROCESS" ? `Process · ${it.uom_primary}` : `Stock item · synced with Accounts inventory · ${it.uom_primary}`}
        actions={
          <>
            <Can permission="operations.items" level="WRITE"><Button asChild><Link href={p(`/items/${it.id}/edit`)}><Pencil /> Edit item</Link></Button></Can>
            <Can permission="operations.runs_execution" level="WRITE"><Button asChild variant="primary"><Link href={p(`/runs/new?item=${it.id}`)}><CirclePlay /> Launch run</Link></Button></Can>
          </>
        }
      />
      <KpiGrid>
        <KpiCard title="Runs" value={s.run_count} icon={CirclePlay} tone="indigo" caption={s.active_run_count ? `${s.active_run_count} active` : "None active"} />
        <KpiCard title="Average yield" value={s.avg_yield_pct ? `${formatQty(s.avg_yield_pct, 1)}%` : "—"} icon={CirclePlay} tone="teal" caption="Accepted ÷ input" />
        <KpiCard title="Average unit cost" value={s.avg_unit_cost ? formatMoney(s.avg_unit_cost) : "—"} icon={CirclePlay} tone="orange" caption={s.last_run_at ? `Last run ${formatDate(s.last_run_at)}` : "No runs yet"} />
      </KpiGrid>
      <div className="grid gap-4 lg:grid-cols-[1fr_1.3fr]">
        <Card title="Profile">
          <KeyValue rows={[
            ["Code", it.sku_code ?? "—"],
            ["Unit", it.uom_primary],
            ["Material", values.material_grade ?? "—"],
            ["Tolerance", values.tolerance ?? "—"],
            ["Cycle time", values.cycle_time_min ? `${values.cycle_time_min} min` : "—"],
            ["Drawing", it.diagram_url ? <a key="d" href={it.diagram_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1">Open drawing{values.drawing_rev ? ` · Rev ${values.drawing_rev}` : ""} <ExternalLink className="size-3" /></a> : values.drawing_rev ? `Rev ${values.drawing_rev}` : "—"],
            ...defs.map((d): [string, string] => [d.label, values[d.key] ? `${values[d.key]}${d.unit ? ` ${d.unit}` : ""}` : "—"]),
          ]} />
        </Card>
        <Card title="Workflows" description="Process flow this item follows" actions={<Can permission="operations.workflows" level="WRITE"><Button asChild size="sm"><Link href={p(`/workflows/new?item=${it.id}`)}>New workflow</Link></Button></Can>}>
          {!workflows.data ? <Skeleton className="h-24" /> : workflows.data.length === 0 ? (
            <EmptyState icon={Workflow} tone="indigo" title="No workflow yet" description="Pick an ISO template and adjust the steps." />
          ) : (
            <ul className="flex flex-col gap-2">
              {workflows.data.map((w) => (
                <li key={w.id}>
                  <Link href={p(`/workflows/${w.id}`)} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5 no-underline hover:border-line-strong">
                    <Workflow className="size-4 text-indigo-text" aria-hidden />
                    <span className="flex-1 text-[13px] font-semibold text-fg">{w.name} · v{w.version}</span>
                    <Badge tone={w.status === "PUBLISHED" ? "success" : "indigo"}>{w.status === "PUBLISHED" ? "Published" : "Draft"}</Badge>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Card title="Run history" description="Unit cost by period">
        <DataTable aria-label="Run history" columns={runCols} data={runs.data} loading={runs.isPending} getRowId={(r) => r.id}
          onRowClick={(r) => router.push(p(`/runs/${r.id}`))}
          empty={<EmptyState title="No runs yet" description="Launch a run to start tracking yield and unit cost." />} />
      </Card>
    </div>
  );
}
