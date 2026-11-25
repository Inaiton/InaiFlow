"use client";

import { AlertTriangle, CirclePlay, Gauge, PackageCheck, ShieldCheck, Smartphone, TriangleAlert } from "lucide-react";
import Link from "next/link";
import {
  Button, Card, EmptyState, ErrorState, GetStartedGuide, Hint, KpiCard, KpiGrid, PageHeader, Skeleton,
} from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { formatDate } from "@/core/dates";
import { formatQty } from "@/core/money";
import { Can } from "@/core/permissions/Can";
import { useOpsDashboard } from "../../api/iso";
import { useOpsItems } from "../../api/items";
import { useRuns } from "../../api/runs";
import { useWorkflows } from "../../api/workflows";
import { useOpsPath } from "../../paths";
import { Progress } from "../shared/Progress";
import { InstrumentBadge, NcrBadge, RunStatusBadge } from "../shared/status";

const KPI_ICONS = [PackageCheck, TriangleAlert, Gauge, ShieldCheck];
const KPI_TONES = ["teal", "danger", "orange", "indigo"] as const;

/** /operations — design Ops-Dashboard: guide, KPIs, active runs, attention list. */
export function OpsDashboard() {
  const p = useOpsPath();
  const dash = useOpsDashboard();
  const items = useOpsItems({ limit: 1, offset: 0 });
  const workflows = useWorkflows();
  const runs = useRuns({ limit: 5, offset: 0 });
  const d = dash.data;

  const hasItem = (items.data?.total ?? 0) > 0;
  const hasWorkflow = (workflows.data ?? []).some((w) => w.status === "PUBLISHED");
  const hasRun = (runs.data?.total ?? 0) > 0;
  const hasQc = (runs.data?.items ?? []).some((r) => r.accepted_qty !== "0" || r.rejected_qty !== "0");
  const allDone = hasItem && hasWorkflow && hasRun && hasQc;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        crumbs={[{ label: "Operations" }, { label: "Overview" }]}
        title="Production & quality"
        description="What’s running this month and what needs you"
        actions={
          <>
            <Button asChild variant="secondary"><Link href={p("/runs")}><Smartphone /> Shop-floor view</Link></Button>
            <Can permission="operations.runs_execution" level="WRITE">
              <Button asChild variant="primary"><Link href={p("/runs/new")}><CirclePlay /> Launch run</Link></Button>
            </Can>
          </>
        }
      />
      {!allDone ? (
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <GetStartedGuide
            title="Get started · takes about 5 minutes"
            steps={[
              { title: "Add an item", description: "The part or process you make", href: p("/items/new"), done: hasItem },
              { title: "Build its workflow", description: "Steps and QC gates, from a template", href: p("/workflows/new"), done: hasWorkflow },
              { title: "Launch a period run", description: "One workflow for one month", href: p("/runs/new"), done: hasRun },
              { title: "Record QC", description: "Quick QC: just count good and rejected", href: p("/runs"), done: hasQc },
            ]}
          />
          <Hint title="New here?">
            A <strong>run</strong> is one workflow executed for one month. If you only count parts, use <strong>Quick QC</strong> — readings
            fill in with the nominal value and are tagged “Auto · nominal” on reports.
          </Hint>
        </div>
      ) : null}
      {dash.isError ? (
        <ErrorState message={describeError(dash.error)} onRetry={() => void dash.refetch()} />
      ) : (
        <KpiGrid>
          {d
            ? d.kpis.slice(0, 4).map((k, i) => (
                <KpiCard
                  key={k.key}
                  title={k.label}
                  value={/pct|yield|rate/i.test(k.key) ? `${formatQty(k.value, 1)}%` : formatQty(k.value, 2)}
                  icon={KPI_ICONS[i % 4]!}
                  tone={KPI_TONES[i % 4]}
                  change={k.change_pct ? { label: `${k.change_pct.startsWith("-") ? "" : "+"}${formatQty(k.change_pct, 1)}%`, tone: k.change_pct.startsWith("-") ? "danger" : "success" } : undefined}
                />
              ))
            : Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-[118px] rounded-2xl" />)}
        </KpiGrid>
      )}
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card title="Active runs" description="Running this month" actions={<Button asChild size="sm" variant="ghost"><Link href={p("/runs")}>All runs</Link></Button>}>
          {!d ? <Skeleton className="h-40" /> : d.active_runs.length === 0 ? (
            <EmptyState icon={CirclePlay} tone="indigo" title="No active runs" description="Launch a run to start recording production." />
          ) : (
            <ul className="flex flex-col gap-2">
              {d.active_runs.map((r) => (
                <li key={r.id}>
                  <Link href={p(`/runs/${r.id}`)} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5 no-underline hover:border-line-strong">
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-[13px] font-semibold text-fg">{r.run_title}</span>
                      <span className="truncate text-xs text-fg-muted">{r.stock_item_name ?? r.workflow_name} · {formatQty(r.planned_qty)} planned · {r.current_step_names.join(", ") || "—"}</span>
                    </span>
                    <Progress className="w-32" value={Number(r.progress_pct)} />
                    <RunStatusBadge status={r.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Needs your attention">
          {!d ? <Skeleton className="h-40" /> : d.open_ncrs.length + d.calibration_due.length === 0 ? (
            <EmptyState icon={ShieldCheck} tone="success" title="All clear" description="No open NCRs or calibrations due." />
          ) : (
            <ul className="flex flex-col gap-2">
              {d.calibration_due.slice(0, 4).map((i) => (
                <li key={i.id} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5">
                  <Gauge className="size-4 text-warning-text" aria-hidden />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-[13px] font-semibold text-fg">{i.instrument_code} · {i.name}</span>
                    <span className="text-xs text-fg-muted">Due {formatDate(i.next_due_date)}</span>
                  </span>
                  <InstrumentBadge status={i.status} />
                </li>
              ))}
              {d.open_ncrs.slice(0, 4).map((n) => (
                <li key={n.id}>
                  <Link href={p(`/iso-compliance/ncr/${n.id}`)} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5 no-underline hover:border-line-strong">
                    <AlertTriangle className="size-4 text-danger-text" aria-hidden />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-[13px] font-semibold text-fg">{n.ncr_number} · {n.run_title ?? "Manual"}</span>
                      <span className="truncate text-xs text-fg-muted">{n.defect_description}</span>
                    </span>
                    <NcrBadge status={n.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {d ? (
            <Link href={p("/iso-compliance")} className="flex flex-col gap-1 no-underline">
              <span className="text-[13px] font-medium text-fg">ISO readiness</span>
              <Progress value={Number(d.readiness_pct)} tone="bg-indigo" label="ISO readiness" />
            </Link>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
