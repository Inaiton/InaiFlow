"use client";

import { useMemo, useState } from "react";
import { Button, ErrorState, Field, NativeSelect, Sheet, SheetContent, Skeleton, Textarea } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { formatDateTime } from "@/core/dates";
import { useCan } from "@/core/permissions/Can";
import { DocumentMultiPicker } from "@/features/documents/public";
import { useChecklist, useUpdateChecklist } from "../../api/iso";
import { CHECKLIST_STATUSES, ChecklistBadge } from "../shared/status";

type Item = Schemas["ChecklistItemOut"];

/** ISO 9001:2015 clause checklist with status, notes and evidence documents. */
export function ChecklistTab() {
  const list = useChecklist();
  const [open, setOpen] = useState<Item | null>(null);
  const groups = useMemo(() => {
    const m = new Map<string, Item[]>();
    for (const it of list.data ?? []) {
      const top = it.clause.split(".")[0] ?? it.clause;
      m.set(top, [...(m.get(top) ?? []), it]);
    }
    return [...m.entries()];
  }, [list.data]);
  if (list.isError) return <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} />;
  if (!list.data) return <Skeleton className="h-60" />;
  return (
    <div className="flex flex-col gap-4 pt-2">
      {groups.map(([clause, items]) => (
        <section key={clause} aria-label={`Clause ${clause}`} className="flex flex-col gap-1">
          <h3 className="m-0 text-[13px] font-semibold text-fg-muted">Clause {clause}</h3>
          {items.map((it) => (
            <button key={it.id} type="button" onClick={() => setOpen(it)} className="flex items-center gap-3 rounded-lg border border-line px-3 py-2 text-left hover:border-line-strong">
              <span className="w-12 text-[12.5px] font-semibold text-fg">{it.clause}</span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13px] text-fg">{it.title}</span>
                {it.evidence_document_ids.length ? <span className="text-[11.5px] text-fg-muted">{it.evidence_document_ids.length} evidence document(s)</span> : null}
              </span>
              <ChecklistBadge status={it.status} />
            </button>
          ))}
        </section>
      ))}
      {open ? <ChecklistSheet key={open.id} item={open} onClose={() => setOpen(null)} /> : null}
    </div>
  );
}

function ChecklistSheet({ item, onClose }: { item: Item; onClose: () => void }) {
  const canWrite = useCan("operations.iso_compliance", "WRITE");
  const update = useUpdateChecklist();
  const [status, setStatus] = useState(item.status);
  const [notes, setNotes] = useState(item.notes ?? "");
  const [evidence, setEvidence] = useState<string[]>(item.evidence_document_ids);
  return (
    <Sheet open onOpenChange={(o) => !o && onClose()}>
      <SheetContent title={`${item.clause} · ${item.title}`} description={item.description ?? undefined} width={520}
        footer={canWrite ? <><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={update.isPending}
          onClick={async () => { await update.mutateAsync({ id: item.id, body: { status, notes: notes || null, evidence_document_ids: evidence } }); onClose(); }}>Save</Button></> : undefined}>
        <fieldset disabled={!canWrite} className="flex flex-col gap-3.5">
          <Field label="Status">
            <NativeSelect value={status} onChange={(e) => setStatus(e.target.value)}>
              {CHECKLIST_STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </NativeSelect>
          </Field>
          <Field label="Notes"><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
          <div className="flex flex-col gap-1.5">
            <span className="text-[12.5px] font-medium text-fg-2">Evidence documents</span>
            <DocumentMultiPicker value={evidence} onChange={setEvidence} disabled={!canWrite} />
          </div>
          {item.updated_at ? <p className="m-0 text-xs text-fg-muted">Last updated by {item.updated_by_name ?? "—"} · {formatDateTime(item.updated_at)}</p> : null}
        </fieldset>
      </SheetContent>
    </Sheet>
  );
}
