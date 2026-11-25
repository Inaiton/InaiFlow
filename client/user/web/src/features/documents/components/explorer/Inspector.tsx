"use client";

import { Download, FolderInput, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import {
  Badge, Button, ConfirmDialog, ErrorState, Input, KeyValue, Sheet, SheetContent, Skeleton, StatusBadge, Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { formatDateTime } from "@/core/dates";
import { formatBytes } from "@/core/upload";
import { useCan } from "@/core/permissions/Can";
import { useDeleteDocument, useDocAudit, useDocument, useExportDocument, useUpdateDocument, useVersions } from "../../api/documents";
import { saveBlob } from "../../lib/transfer";
import { ApprovalPanel } from "../approval/ApprovalPanel";
import { DocPreview } from "./DocPreview";
import { FolderPickerDialog } from "./FolderPickerDialog";

/** Right drawer (design Doc-Viewer): preview, details & approval, versions, history. */
export function Inspector({ docId, onClose, onOpenDoc }: { docId: string | null; onClose: () => void; onOpenDoc: (id: string) => void }) {
  const doc = useDocument(docId);
  return (
    <Sheet open={Boolean(docId)} onOpenChange={(o) => !o && onClose()}>
      <SheetContent title={doc.data?.title ?? "Document"} description={doc.data ? doc.data.folder_path.join(" / ") : undefined} width={620}>
        {doc.isError ? <ErrorState message={describeError(doc.error)} onRetry={() => void doc.refetch()} /> : !doc.data ? <Skeleton className="h-80" /> : (
          <InspectorBody key={doc.data.id + doc.data.updated_at} doc={doc.data} onClose={onClose} onOpenDoc={onOpenDoc} />
        )}
      </SheetContent>
    </Sheet>
  );
}

function InspectorBody({ doc, onClose, onOpenDoc }: { doc: NonNullable<ReturnType<typeof useDocument>["data"]>; onClose: () => void; onOpenDoc: (id: string) => void }) {
  const canEdit = useCan("documents.editor", "WRITE");
  const canDelete = useCan("documents.explorer", "FULL");
  const [tab, setTab] = useState("preview");
  const versions = useVersions(tab === "versions" ? doc.id : null);
  const audit = useDocAudit(doc.id, tab === "history");
  const update = useUpdateDocument(doc.id);
  const del = useDeleteDocument();
  const exp = useExportDocument(doc.id);
  const [title, setTitle] = useState(doc.title);
  const [isoNo, setIsoNo] = useState(doc.iso_doc_number ?? "");
  const [moving, setMoving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const editable = canEdit && doc.approval_status === "DRAFT";
  const exportAs = async (f: "pdf" | "docx") => {
    try { saveBlob(await exp.mutateAsync(f), `${doc.title}.${f}`); } catch (e) { toast.error(describeError(e)); }
  };
  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList>
        <TabsTrigger value="preview">Preview</TabsTrigger>
        <TabsTrigger value="details">Details & approval</TabsTrigger>
        <TabsTrigger value="versions">Versions</TabsTrigger>
        <TabsTrigger value="history">History</TabsTrigger>
      </TabsList>
      <TabsContent value="preview"><div className="pt-3"><DocPreview doc={doc} /></div></TabsContent>
      <TabsContent value="details">
        <div className="flex flex-col gap-4 pt-3">
          <ApprovalPanel doc={doc} compact onRevised={(d) => onOpenDoc(d.id)} />
          <KeyValue rows={[
            ["Status", <StatusBadge key="s" status={doc.approval_status} />],
            ["Title", editable ? <Input key="t" value={title} onChange={(e) => setTitle(e.target.value)} onBlur={() => title.trim() && title !== doc.title && update.mutate({ title: title.trim() })} /> : doc.title],
            ["ISO document no.", editable ? <Input key="i" value={isoNo} placeholder="SOP-PRD-12" onChange={(e) => setIsoNo(e.target.value)} onBlur={() => isoNo !== (doc.iso_doc_number ?? "") && update.mutate({ iso_doc_number: isoNo || null })} /> : doc.iso_doc_number ?? "—"],
            ["Revision", `Rev ${doc.revision_no}`],
            ["Source", doc.source_type.replace(/_/g, " ").toLowerCase()],
            ["File", doc.file_name ? `${doc.file_name}${doc.file_size ? ` · ${formatBytes(doc.file_size)}` : ""}` : "Report"],
            ["Prepared by", `${doc.prepared_by_name} · ${formatDateTime(doc.created_at)}`],
            ["Linked to", [doc.linked_period_run_id && "run", doc.linked_step_id && "step", doc.linked_voucher_id && "voucher", doc.linked_stock_item_id && "item"].filter(Boolean).join(", ") || "—"],
          ]} />
          <div className="flex flex-wrap gap-2">
            {!doc.file_mime_type ? <><Button size="sm" onClick={() => void exportAs("pdf")} loading={exp.isPending}><Download /> PDF</Button><Button size="sm" onClick={() => void exportAs("docx")}><Download /> Word</Button></> : null}
            {canEdit ? <Button size="sm" onClick={() => setMoving(true)}><FolderInput /> Move</Button> : null}
            {canDelete ? <Button size="sm" variant="destructive" disabled={!doc.can_delete} title={doc.can_delete ? undefined : "Approved, obsolete or linked documents can’t be deleted"} onClick={() => setDeleting(true)}><Trash2 /> Delete</Button> : null}
          </div>
        </div>
      </TabsContent>
      <TabsContent value="versions">
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0 pt-3">
          {!versions.data ? <Skeleton className="h-24" /> : versions.data.map((v) => (
            <li key={v.id}>
              <button type="button" onClick={() => onOpenDoc(v.id)} className="flex w-full items-center gap-2 rounded-lg border border-line px-3 py-2 text-left text-[13px] hover:border-line-strong" aria-current={v.id === doc.id ? "true" : undefined}>
                <span className="font-semibold text-fg">Rev {v.revision_no}</span>
                <span className="flex-1 truncate text-fg-muted">{v.prepared_by_name} · {formatDateTime(v.updated_at)}</span>
                {v.id === doc.id ? <Badge>Viewing</Badge> : null}
                <StatusBadge status={v.approval_status} />
              </button>
            </li>
          ))}
        </ul>
      </TabsContent>
      <TabsContent value="history">
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0 pt-3">
          {!audit.data ? <Skeleton className="h-24" /> : audit.data.length === 0 ? <li className="text-[13px] text-fg-muted">No events yet.</li> : audit.data.map((a) => (
            <li key={a.id} className="rounded-lg bg-canvas px-3 py-2 text-[12.5px]">
              <span className="font-semibold text-fg">{a.action.replace(/_/g, " ").toLowerCase()}</span> · {a.user_name ?? a.actor_type} · {formatDateTime(a.created_at)}
              {a.reason ? <span className="block text-fg-muted">“{a.reason}”</span> : null}
            </li>
          ))}
        </ul>
      </TabsContent>
      <FolderPickerDialog open={moving} onOpenChange={setMoving} title="Move document to…" confirmLabel="Move here" loading={update.isPending}
        onPick={async (f) => { await update.mutateAsync({ folder_id: f.id }); setMoving(false); }} />
      <ConfirmDialog open={deleting} onOpenChange={setDeleting} title="Delete this document?" description="This can’t be undone." destructive confirmLabel="Delete" loading={del.isPending}
        onConfirm={async () => { await del.mutateAsync(doc.id); setDeleting(false); onClose(); }} />
    </Tabs>
  );
}
