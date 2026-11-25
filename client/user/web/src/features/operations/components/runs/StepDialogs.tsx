"use client";

import { useState } from "react";
import { ConfirmDialog, Dialog, DialogContent } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { formatQty } from "@/core/money";
import { useReopenStep, useSkipStep, useSucceedStep } from "../../api/runs";
import type { WorkflowNode } from "../../lib/graph";
import { StepEntryForm, type EntryMode } from "./StepEntryForm";

type Step = Schemas["StepOut"];
export type StepDialog = { kind: "entry"; mode: EntryMode } | { kind: "skip" } | { kind: "succeed" } | { kind: "reopen" } | null;

export function StepDialogs({ runId, step, node, dialog, onClose }: { runId: string; step: Step; node: WorkflowNode | undefined; dialog: StepDialog; onClose: () => void }) {
  const skip = useSkipStep(runId);
  const succeed = useSucceedStep(runId);
  const reopen = useReopenStep(runId);
  const [skipKey] = useState(() => crypto.randomUUID());
  const [okKey] = useState(() => crypto.randomUUID());
  return (
    <>
      <Dialog open={dialog?.kind === "entry"} onOpenChange={(o) => !o && onClose()}>
        <DialogContent size="lg" title={`${dialog?.kind === "entry" && dialog.mode === "quick" ? "Quick QC" : "Record"} · ${step.step_name}`} description={`${formatQty(step.input_qty)} units arrived at this step`}>
          {dialog?.kind === "entry" ? <StepEntryForm runId={runId} step={step} node={node} initialMode={dialog.mode} onDone={onClose} onCancel={onClose} /> : null}
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={dialog?.kind === "skip"}
        onOpenChange={(o) => !o && onClose()}
        title={`Skip “${step.step_name}”?`}
        description={`All ${formatQty(step.input_qty)} units move straight to the next step. The skip and your reason are recorded.`}
        confirmLabel="Skip step"
        requireReason
        loading={skip.isPending}
        onConfirm={async (reason) => { await skip.mutateAsync({ stepId: step.id, key: skipKey, body: { reason } }); onClose(); }}
      />
      <SucceedDialog open={dialog?.kind === "succeed"} step={step} loading={succeed.isPending} onClose={onClose}
        onConfirm={async (reason) => { await succeed.mutateAsync({ stepId: step.id, key: okKey, body: { reason: reason || null } }); onClose(); }} />
      <ConfirmDialog
        open={dialog?.kind === "reopen"}
        onOpenChange={(o) => !o && onClose()}
        title="Reopen a signed-off step"
        description="Unlocks the step so it can be corrected. This is an audited override."
        confirmLabel="Reopen step"
        destructive
        requireReason
        reasonLabel="Override reason (recorded in audit log)"
        loading={reopen.isPending}
        onConfirm={async (reason) => { await reopen.mutateAsync({ stepId: step.id, reason }); onClose(); }}
      />
    </>
  );
}

function SucceedDialog({ open, step, loading, onClose, onConfirm }: { open: boolean; step: Step; loading: boolean; onClose: () => void; onConfirm: (reason: string) => Promise<void> }) {
  const [reason, setReason] = useState("");
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={(o) => { if (!o) { setReason(""); onClose(); } }}
      title={`Mark “${step.step_name}” as success?`}
      description={`Accepts all ${formatQty(step.input_qty)} units without readings.`}
      confirmLabel="Mark success"
      loading={loading}
      onConfirm={() => onConfirm(reason)}
    >
      <label className="flex flex-col gap-1.5 text-[12.5px] font-medium text-fg-2">
        Note (optional)
        <textarea className="min-h-16 rounded-lg border border-line px-2.5 py-2 text-[13px]" value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
    </ConfirmDialog>
  );
}
