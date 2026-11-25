"use client";

import { ArchiveX, CheckCircle2, FilePlus2, Send, ShieldCheck, Undo2 } from "lucide-react";
import { useRef, useState } from "react";
import { Button, ConfirmDialog, Hint } from "@/components/ui";
import { ApiError } from "@/core/api/errors";
import { describeError } from "@/core/api/error-messages";
import { formatDateTime } from "@/core/dates";
import { useCan } from "@/core/permissions/Can";
import { cn } from "@/lib/utils";
import { useReview, useRevise, useTransition, type DocumentOut } from "../../api/documents";

type Pending = "submit" | "review" | "reject" | "approve" | "obsolete" | null;

function friendly(e: unknown): string {
  if (e instanceof ApiError && e.code === "SEGREGATION_OF_DUTIES") return "You prepared this document, so a different person has to review or approve it. Ask a QA lead or admin.";
  if (e instanceof ApiError && e.code === "INVALID_STATE") return "This document changed state meanwhile — refresh and try again.";
  return describeError(e);
}

/** ISO 7.5 stamps (Prepared → Reviewed → Approved) and the next action for the current state. */
export function ApprovalPanel({ doc, onRevised, compact }: { doc: DocumentOut; onRevised?: (d: DocumentOut) => void; compact?: boolean }) {
  const canEdit = useCan("documents.editor", "WRITE");
  const canReview = useCan("documents.iso_approval", "WRITE");
  const canApprove = useCan("documents.iso_approval", "FULL");
  const transition = useTransition(doc.id);
  const review = useReview(doc.id);
  const revise = useRevise(doc.id);
  const [pending, setPending] = useState<Pending>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const s = doc.approval_status;
  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); setPending(null); } catch (e) { setError(friendly(e)); setPending(null); }
  };
  const doRevise = async (file?: File) => {
    setError(null);
    try { const d = await revise.mutateAsync(file); onRevised?.(d); } catch (e) { setError(friendly(e)); }
  };
  const stamps: [string, string | null, string | null][] = [
    ["Prepared", doc.prepared_by_name, formatDateTime(doc.created_at)],
    ["Reviewed", doc.reviewed_by_name, doc.review_comment],
    ["Approved", doc.approved_by_name, doc.approved_at ? formatDateTime(doc.approved_at) : null],
  ];
  const isFile = Boolean(doc.file_mime_type);
  return (
    <section aria-label="Approval" className="flex flex-col gap-3">
      <ol className={cn("m-0 grid list-none gap-2 p-0", compact ? "grid-cols-1" : "sm:grid-cols-3")}>
        {stamps.map(([label, who, sub]) => (
          <li key={label} className={cn("flex items-center gap-2 rounded-xl border px-3 py-2", who ? "border-success/40 bg-success-tint" : "border-line bg-canvas")}>
            {who ? <CheckCircle2 className="size-4 flex-none text-success" aria-hidden /> : <span className="size-4 flex-none rounded-full border-2 border-line-strong" aria-hidden />}
            <span className="flex min-w-0 flex-col">
              <span className="text-[11px] font-semibold tracking-wide text-fg-muted uppercase">{label} · Rev {doc.revision_no}</span>
              <span className="truncate text-[13px] text-fg">{who ?? "Pending"}</span>
              {who && sub ? <span className="truncate text-[11.5px] text-fg-muted">{sub}</span> : null}
            </span>
          </li>
        ))}
      </ol>
      {error ? <Hint tone="danger">{error}</Hint> : null}
      <div className="flex flex-wrap gap-2">
        {s === "DRAFT" && canEdit ? <Button variant="primary" onClick={() => setPending("submit")}><Send /> Send for review</Button> : null}
        {s === "UNDER_REVIEW" && !doc.reviewed_by_name && canReview ? <Button variant="primary" onClick={() => setPending("review")}><ShieldCheck /> Mark reviewed</Button> : null}
        {s === "UNDER_REVIEW" && doc.reviewed_by_name && canApprove ? <Button variant="primary" onClick={() => setPending("approve")}><CheckCircle2 /> Approve & release</Button> : null}
        {s === "UNDER_REVIEW" && (canReview || canEdit) ? <Button onClick={() => setPending("reject")}><Undo2 /> Send back</Button> : null}
        {s === "APPROVED" && canEdit ? (
          isFile ? (
            <>
              <input ref={fileRef} type="file" className="sr-only" aria-label="New revision file" onChange={(e) => { const f = e.target.files?.[0]; if (f) void doRevise(f); e.target.value = ""; }} />
              <Button loading={revise.isPending} onClick={() => fileRef.current?.click()}><FilePlus2 /> Upload new revision</Button>
            </>
          ) : <Button loading={revise.isPending} onClick={() => void doRevise()}><FilePlus2 /> Start revision {doc.revision_no + 1}</Button>
        ) : null}
        {s === "APPROVED" && canApprove ? <Button variant="destructive" onClick={() => setPending("obsolete")}><ArchiveX /> Mark obsolete</Button> : null}
      </div>
      <ConfirmDialog open={pending === "submit"} onOpenChange={(o) => !o && setPending(null)} title="Send for review?" description="The document is locked for editing while it is reviewed."
        confirmLabel="Send for review" loading={transition.isPending} onConfirm={() => run(() => transition.mutateAsync({ to: "UNDER_REVIEW" }))} />
      <ConfirmDialog open={pending === "review"} onOpenChange={(o) => !o && setPending(null)} title="Mark as reviewed" description="Your name is stamped as reviewer. An approver then releases it."
        confirmLabel="Mark reviewed" loading={review.isPending} requireReason reasonLabel="Review comment" onConfirm={(c) => run(() => review.mutateAsync({ comment: c }))} />
      <ConfirmDialog open={pending === "approve"} onOpenChange={(o) => !o && setPending(null)} title={`Approve revision ${doc.revision_no}?`}
        description="It becomes the released version; earlier revisions with the same document number are marked obsolete."
        confirmLabel="Approve & release" loading={transition.isPending} onConfirm={() => run(() => transition.mutateAsync({ to: "APPROVED" }))} />
      <ConfirmDialog open={pending === "reject"} onOpenChange={(o) => !o && setPending(null)} title="Send back to draft" description="Tell the preparer what to change."
        confirmLabel="Send back" requireReason reasonLabel="What needs to change" loading={transition.isPending} onConfirm={(c) => run(() => transition.mutateAsync({ to: "DRAFT", comment: c }))} />
      <ConfirmDialog open={pending === "obsolete"} onOpenChange={(o) => !o && setPending(null)} title="Mark obsolete?" description="It stays in the archive, watermarked as superseded, and can’t be used any more."
        destructive confirmLabel="Mark obsolete" requireReason loading={transition.isPending} onConfirm={(c) => run(() => transition.mutateAsync({ to: "OBSOLETE", comment: c }))} />
    </section>
  );
}
