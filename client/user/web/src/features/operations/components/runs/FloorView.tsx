"use client";

import { ArrowLeft, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button, EmptyState, ErrorState, Hint, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { formatQty } from "@/core/money";
import { useCan } from "@/core/permissions/Can";
import { useRun } from "../../api/runs";
import { useOpsPath } from "../../paths";
import { StepStatusBadge } from "../shared/status";
import { StepEntryForm } from "./StepEntryForm";

/** /operations/runs/[runId]/floor — big-touch shop-floor entry (design Ops-Floor-Mobile). */
export function FloorView({ runId }: { runId: string }) {
  const p = useOpsPath();
  const run = useRun(runId);
  const canRun = useCan("operations.runs_execution", "WRITE");
  const [stepId, setStepId] = useState<string | null>(null);
  if (run.isError) return <ErrorState message={describeError(run.error)} onRetry={() => void run.refetch()} />;
  const r = run.data;
  if (!r) return <Skeleton className="h-96" />;
  const active = r.steps.filter((s) => s.status === "ACTIVE");
  const step = r.steps.find((s) => s.id === stepId);
  const node = step ? r.graph_snapshot.nodes.find((n) => n.id === step.node_id) : undefined;
  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-4">
      <div className="flex items-center gap-2">
        <Button asChild size="icon" variant="ghost" aria-label="Back to run"><Link href={step ? "#" : p(`/runs/${r.id}`)} onClick={(e) => { if (step) { e.preventDefault(); setStepId(null); } }}><ArrowLeft /></Link></Button>
        <div className="flex min-w-0 flex-col">
          <h1 className="m-0 truncate text-lg font-semibold text-ink">{step ? step.step_name : r.run_title}</h1>
          <span className="text-xs text-fg-muted">{step ? `${formatQty(step.input_qty)} units arrived` : `${formatQty(r.accepted_qty)} accepted of ${formatQty(r.planned_qty)}`}</span>
        </div>
      </div>
      {r.status !== "IN_PROGRESS" ? <Hint tone="warning">This run is not in progress — nothing to record right now.</Hint> : null}
      {step ? (
        <StepEntryForm runId={r.id} step={step} node={node} initialMode="quick" onDone={() => setStepId(null)} onCancel={() => setStepId(null)} />
      ) : active.length === 0 ? (
        <EmptyState icon={CheckCircle2} tone="success" title="No steps waiting" description="All caught up on this run." />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {active.map((s) => (
            <li key={s.id}>
              <button type="button" disabled={!canRun || r.status !== "IN_PROGRESS"} onClick={() => setStepId(s.id)}
                className="flex w-full items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-4 text-left disabled:opacity-60">
                <span className="flex flex-1 flex-col">
                  <span className="text-base font-semibold text-fg">{s.step_name}</span>
                  <span className="text-[13px] text-fg-muted">{formatQty(s.input_qty)} units waiting · tap to count</span>
                </span>
                <StepStatusBadge status={s.status} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
