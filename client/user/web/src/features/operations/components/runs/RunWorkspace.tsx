"use client";

import { Smartphone } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { Button, Card, ErrorState, Hint, PageHeader, Segmented, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { formatDate } from "@/core/dates";
import { formatMoney, formatQty } from "@/core/money";
import { useCan } from "@/core/permissions/Can";
import { useRun } from "../../api/runs";
import { takenEdges } from "../../lib/graph";
import { useOpsPath } from "../../paths";
import { RUN_LABEL, RunStatusBadge, periodLabel } from "../shared/status";
import { MoneyFlowPanel } from "./MoneyFlowPanel";
import { RunActions } from "./RunActions";
import { StepLogTable } from "./StepLogTable";
import { StepPanel } from "./StepPanel";

const FlowCanvas = dynamic(() => import("../shared/FlowCanvas"), { ssr: false, loading: () => <Skeleton className="h-full w-full" /> });

/** /operations/runs/[runId] — run workspace (design Ops-Run): pipeline, step panel, money flow. */
export function RunWorkspace({ runId }: { runId: string }) {
  const p = useOpsPath();
  const run = useRun(runId);
  const canMoney = useCan("operations.runs_accounting", "READ");
  const [picked, setPicked] = useState<string | null>(null);
  const [view, setView] = useState<"flow" | "table">("flow");
  const r = run.data;
  const graph = r?.graph_snapshot;
  const taken = useMemo(() => (r ? takenEdges(r.graph_snapshot, r.steps) : new Map<string, string>()), [r]);
  const byNode = useMemo(() => new Map((r?.steps ?? []).map((s) => [s.node_id, s])), [r]);
  const decorate = useCallback((nodeId: string) => {
    const s = byNode.get(nodeId);
    if (!s) return {};
    const detail = s.executed_at ? `${formatQty(s.input_qty)} in · ${formatQty(s.accepted_qty)} ok${s.rejected_qty !== "0" ? ` · ${formatQty(s.rejected_qty)} rej` : ""}` : s.status === "ACTIVE" ? `${formatQty(s.input_qty)} waiting` : undefined;
    return { status: s.status, detail, locked: s.is_locked };
  }, [byNode]);

  if (run.isError) return <ErrorState message={describeError(run.error)} onRetry={() => void run.refetch()} />;
  if (!r || !graph) return <Skeleton className="h-[70vh]" />;
  const active = r.steps.filter((s) => s.status === "ACTIVE");
  const selected = r.steps.find((s) => s.id === picked) ?? active[0] ?? [...r.steps].sort((a, b) => a.sequence - b.sequence)[0];
  const selectedNodeId = selected?.node_id ?? null;
  const stats: [string, string][] = [
    ["Planned", formatQty(r.planned_qty)], ["Accepted", formatQty(r.accepted_qty)], ["Rejected", formatQty(r.rejected_qty)], ["Rework", formatQty(r.rework_qty)],
    ["Yield", r.yield_pct ? `${formatQty(r.yield_pct, 1)}%` : "—"], ...(canMoney ? [["Unit cost", formatMoney(r.computed_unit_cost)] as [string, string]] : []),
  ];
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumbs={[{ label: "Operations", href: p() }, { label: "Period runs", href: p("/runs") }, { label: r.run_title }]}
        title={<span className="flex flex-wrap items-center gap-2">{r.run_title} <RunStatusBadge status={r.status} /></span>}
        description={`${r.stock_item_name ?? r.workflow_name} · ${periodLabel(r.period_month)} · ${r.started_at ? `started ${formatDate(r.started_at)}` : RUN_LABEL[r.status]} · ${r.workflow_name} v${r.workflow_version}`}
        actions={<><Button asChild size="icon" aria-label="Shop-floor view"><Link href={p(`/runs/${r.id}/floor`)}><Smartphone /></Link></Button><RunActions run={r} /></>}
      />
      <section aria-label="Run totals" className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-xl bg-muted-surface px-3 py-2">
            <div className="text-[11.5px] text-fg-muted">{k}</div>
            <div className="tabular text-lg font-semibold text-ink">{v}</div>
          </div>
        ))}
      </section>
      {r.status === "QC_HOLD" && r.hold_reason ? <Hint tone="warning" title="On QC hold">{r.hold_reason}</Hint> : null}
      {r.status === "CANCELLED" && r.cancel_reason ? <Hint tone="danger" title="Cancelled">{r.cancel_reason}</Hint> : null}
      {active.length && r.status === "IN_PROGRESS" ? (
        <Hint tone="sky" title={`Next: ${active.map((s) => s.step_name).join(" ‖ ")}`}>{active.map((s) => `${formatQty(s.input_qty)} units at ${s.step_name}`).join(" · ")}</Hint>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card padded={false} className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3">
            <span className="text-[12.5px] text-fg-muted">Click any step to open it · counts show units on each branch</span>
            <Segmented aria-label="View" value={view} onChange={setView} options={[{ value: "flow", label: "Flow" }, { value: "table", label: "Table" }]} />
          </div>
          {view === "flow" ? (
            <div style={{ height: "min(64vh, 640px)" }} className="mt-2 border-t border-line bg-canvas">
              <FlowCanvas graph={graph} readOnly selectedId={selectedNodeId} decorate={decorate} taken={taken}
                onSelect={(sel) => { if (sel?.kind === "node") setPicked(byNode.get(sel.id)?.id ?? null); }} />
            </div>
          ) : (
            <div className="px-4 pb-4"><StepLogTable steps={r.steps} onPick={(s) => setPicked(s.id)} /></div>
          )}
          <div className="flex flex-wrap gap-3 border-t border-line px-4 py-2 text-[11.5px] text-fg-muted" aria-label="Legend">
            {[["bg-success", "Done"], ["bg-sky", "Running"], ["bg-teal", "Signed off"], ["bg-fg-faint", "Waiting"], ["bg-danger", "Rejected"], ["bg-violet", "Skipped"]].map(([c, l]) => (
              <span key={l} className="flex items-center gap-1.5"><span className={`size-2 rounded-[2px] ${c}`} />{l}</span>
            ))}
          </div>
        </Card>
        <aside className="rounded-2xl border border-line bg-surface px-4 py-4">
          {selected ? <StepPanel key={selected.id} run={r} step={selected} graph={graph} /> : <p className="text-fg-muted">No steps.</p>}
        </aside>
      </div>
      {canMoney ? <MoneyFlowPanel run={r} /> : null}
    </div>
  );
}
