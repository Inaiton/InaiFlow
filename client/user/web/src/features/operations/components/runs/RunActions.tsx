"use client";

import { Download, MoreHorizontal, Pause, Play, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button, ConfirmDialog, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { useCan } from "@/core/permissions/Can";
import { saveBlob } from "@/features/documents/public";
import { useDossier, useRunAction, useRunReasonAction } from "../../api/runs";

type Run = Schemas["RunOut"];

/** Header actions: dossier export, hold/resume/cancel and the one primary action (start or close). */
export function RunActions({ run }: { run: Run }) {
  const canRun = useCan("operations.runs_execution", "WRITE");
  const canFull = useCan("operations.runs_execution", "FULL");
  const start = useRunAction(run.id, "start");
  const resume = useRunAction(run.id, "resume");
  const complete = useRunAction(run.id, "complete");
  const hold = useRunReasonAction(run.id, "hold");
  const cancel = useRunReasonAction(run.id, "cancel");
  const dossier = useDossier(run.id);
  const [dlg, setDlg] = useState<"hold" | "cancel" | "complete" | null>(null);
  const open = run.status !== "COMPLETED" && run.status !== "CANCELLED";
  const allDone = run.steps.every((s) => s.status === "PASSED" || s.status === "SKIPPED" || s.status === "LOCKED" || s.status === "PENDING")
    && run.steps.some((s) => s.node_shape === "TERMINATOR" && s.executed_at);

  const download = async (format: "pdf" | "docx") => {
    try {
      const blob = await dossier.mutateAsync(format);
      saveBlob(blob, `${run.run_title} — dossier.${format}`);
    } catch (e) {
      toast.error(describeError(e));
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild><Button loading={dossier.isPending}><Download /> Dossier</Button></DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onSelect={() => void download("pdf")}>Download PDF</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => void download("docx")}>Download Word (.docx)</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {open && canRun ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button size="icon" aria-label="More run actions"><MoreHorizontal /></Button></DropdownMenuTrigger>
          <DropdownMenuContent>
            {run.status === "IN_PROGRESS" ? <DropdownMenuItem onSelect={() => setDlg("hold")}><Pause className="size-4" /> Put on QC hold</DropdownMenuItem> : null}
            {run.status === "QC_HOLD" ? <DropdownMenuItem onSelect={() => resume.mutate()}><Play className="size-4" /> Resume run</DropdownMenuItem> : null}
            {canFull ? <DropdownMenuItem destructive onSelect={() => setDlg("cancel")}><XCircle className="size-4" /> Cancel run</DropdownMenuItem> : null}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
      {run.status === "PLANNED" && canRun ? <Button variant="primary" loading={start.isPending} onClick={() => start.mutate()}><Play /> Start run</Button> : null}
      {run.status === "IN_PROGRESS" && canFull ? (
        <Button variant={allDone ? "primary" : "secondary"} onClick={() => setDlg("complete")}>Close run</Button>
      ) : null}
      <ConfirmDialog open={dlg === "hold"} onOpenChange={(o) => !o && setDlg(null)} title="Put the run on QC hold?" description="Nobody can record steps until it is resumed." requireReason confirmLabel="Hold run"
        loading={hold.isPending} onConfirm={async (r) => { await hold.mutateAsync(r); setDlg(null); }} />
      <ConfirmDialog open={dlg === "cancel"} onOpenChange={(o) => !o && setDlg(null)} title="Cancel this run?" description="The run stops for good. Posted vouchers stay in Accounts." requireReason destructive confirmLabel="Cancel run"
        loading={cancel.isPending} onConfirm={async (r) => { await cancel.mutateAsync(r); setDlg(null); }} />
      <ConfirmDialog open={dlg === "complete"} onOpenChange={(o) => !o && setDlg(null)} title="Close the run and post costing?"
        description="Posts the Manufacturing Journal (raw material consumed, finished goods at unit cost, scrap) and freezes the unit cost. Every reachable step must be done."
        confirmLabel="Close run" loading={complete.isPending} onConfirm={async () => { await complete.mutateAsync(); setDlg(null); }} />
    </>
  );
}
