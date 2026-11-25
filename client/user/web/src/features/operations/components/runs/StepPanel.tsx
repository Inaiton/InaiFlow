"use client";

import { ClipboardCheck, FastForward, Lock, LockOpen, PenLine, Zap } from "lucide-react";
import { useState } from "react";
import { AdvancedSection, Button, Hint, KeyValue } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { formatDateTime } from "@/core/dates";
import { cmp, formatQty } from "@/core/money";
import { useCan } from "@/core/permissions/Can";
import { useSignoffStep } from "../../api/runs";
import { SHAPE_LABEL, type WorkflowGraph } from "../../lib/graph";
import { toleranceHint } from "../../lib/tolerance";
import { StepStatusBadge } from "../shared/status";
import { StepAttachments } from "./StepAttachments";
import { StepDialogs, type StepDialog } from "./StepDialogs";

type Run = Schemas["RunOut"];
type Step = Schemas["StepOut"];

/** Selected-step panel (design Ops-Run right panel): status, where units went, the three big actions. */
export function StepPanel({ run, step, graph }: { run: Run; step: Step; graph: WorkflowGraph }) {
  const canRun = useCan("operations.runs_execution", "WRITE");
  const canSign = useCan("operations.qc_signoff", "WRITE");
  const canOverride = useCan("operations.qc_signoff", "FULL");
  const signoff = useSignoffStep(run.id);
  const [dialog, setDialog] = useState<StepDialog>(null);
  const node = graph.nodes.find((n) => n.id === step.node_id);
  const live = run.status === "IN_PROGRESS";
  const actionable = live && canRun && step.status === "ACTIVE";
  const executed = Boolean(step.executed_at) && step.status !== "PENDING";
  const name = (id: string) => graph.nodes.find((n) => n.id === id)?.label ?? id;
  const outs = graph.edges.filter((e) => e.source === step.node_id);
  const qtyFor = (b: string) => (b === "REJECT" ? step.rejected_qty : b === "REWORK" ? step.rework_qty : step.status === "SKIPPED" ? step.input_qty : step.accepted_qty);

  return (
    <section aria-label="Step" className="flex flex-col gap-4">
      <div className="flex items-start gap-2">
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-[11px] font-semibold tracking-wide text-fg-muted uppercase">{SHAPE_LABEL[step.node_shape]} · step {step.sequence + 1}</span>
          <h2 className="m-0 truncate text-base font-semibold text-fg">{step.step_name}</h2>
        </div>
        <StepStatusBadge status={step.status} />
      </div>
      {step.is_locked ? (
        <Hint tone="teal" title="Signed off & locked"><Lock className="mr-1 inline size-3.5" />{step.signed_off_by_name} · {formatDateTime(step.signed_off_at)}</Hint>
      ) : null}
      {step.status === "PENDING" ? <p className="m-0 text-[13px] text-fg-muted">Waiting for earlier steps.</p> : null}
      {!live && run.status !== "COMPLETED" && step.status === "ACTIVE" ? <Hint tone="warning">The run is {run.status === "QC_HOLD" ? "on QC hold" : "not started"} — resume it to record this step.</Hint> : null}
      {actionable ? (
        <div className="flex flex-col gap-2">
          <p className="m-0 text-[12.5px] text-fg-muted">{formatQty(step.input_qty)} units waiting · count good and rejected parts — Quick QC fills the readings for you</p>
          <Button variant="primary" size="lg" onClick={() => setDialog({ kind: "entry", mode: "quick" })}><Zap /> Quick QC entry</Button>
          <div className="grid grid-cols-3 gap-2">
            <Button onClick={() => setDialog({ kind: "entry", mode: "full" })}><PenLine /> Record</Button>
            <Button onClick={() => setDialog({ kind: "succeed" })}><ClipboardCheck /> Success</Button>
            <Button disabled={!node?.config.skippable} title={node?.config.skippable ? undefined : "This step can’t be skipped"} onClick={() => setDialog({ kind: "skip" })}><FastForward /> Skip</Button>
          </div>
        </div>
      ) : null}
      {executed ? (
        <>
          <KeyValue rows={[
            ["Input", formatQty(step.input_qty)], ["Accepted", formatQty(step.accepted_qty)], ["Rejected", formatQty(step.rejected_qty)], ["Rework", formatQty(step.rework_qty)],
            ["Recorded by", `${step.executed_by_name ?? "—"} · ${formatDateTime(step.executed_at)}`],
            ...(step.quick_qc ? [["Entry", "Quick QC · readings auto-filled"] as [string, string]] : []),
            ...(step.skip_reason ? [["Skipped because", step.skip_reason] as [string, string]] : []),
            ...(step.override_reason ? [["Override", step.override_reason] as [string, string]] : []),
          ]} />
          {outs.length ? (
            <div className="flex flex-col gap-1.5">
              <h3 className="m-0 text-[13px] font-semibold text-fg">Where units went</h3>
              {outs.map((e) => (
                <div key={e.id} className="flex items-center justify-between rounded-lg bg-canvas px-2.5 py-1.5 text-[12.5px]">
                  <span>{e.branch === "REJECT" ? "Reject" : e.branch === "REWORK" ? "Rework" : "Pass"} → {name(e.target)}</span>
                  <span className={cmp(qtyFor(e.branch), "0") > 0 ? "tabular font-semibold text-fg" : "tabular text-fg-faint"}>{formatQty(qtyFor(e.branch))}</span>
                </div>
              ))}
            </div>
          ) : null}
          {(node?.config.qc_fields ?? []).length ? (
            <KeyValue rows={(node?.config.qc_fields ?? []).map((f) => {
              const r = step.qc_measurements[f.key];
              return [f.label, r?.value ? `${r.value}${r.auto_filled ? " · auto" : ""}${r.in_tolerance === false ? " · out" : ""}` : `— (${toleranceHint(f)})`];
            })} />
          ) : null}
          {canSign && !step.is_locked && live ? (
            <Button variant="primary" loading={signoff.isPending} onClick={() => signoff.mutate(step.id)}><Lock /> Sign off & lock</Button>
          ) : null}
          {canOverride && step.is_locked && run.status !== "COMPLETED" ? (
            <Button variant="destructive" onClick={() => setDialog({ kind: "reopen" })}><LockOpen /> Reopen with override</Button>
          ) : null}
        </>
      ) : null}
      <AdvancedSection title="Attachments & reports" description={`${step.attachment_count} file(s) on this step`}>
        <StepAttachments run={run} step={step} reportTemplateId={node?.config.report_template_id ?? null} />
      </AdvancedSection>
      <StepDialogs runId={run.id} step={step} node={node} dialog={dialog} onClose={() => setDialog(null)} />
    </section>
  );
}
