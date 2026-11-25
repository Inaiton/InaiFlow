"use client";

import { CheckCircle2, FileUp, XCircle } from "lucide-react";
import { useRef, useState } from "react";
import { Button, Dialog, DialogContent, Hint } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { formatBytes, validateFile } from "@/core/upload";
import { cn } from "@/lib/utils";
import { useUploadDocument } from "../../api/documents";
import type { FolderOut } from "../../api/folders";
import { ALLOWED_MIME, titleFromFile } from "../../lib/transfer";
import { FolderPickerDialog } from "./FolderPickerDialog";

type Row = { file: File; pct: number; state: "queued" | "uploading" | "done" | "error"; error?: string };

/** Multi-file upload with per-file progress (design Doc-Upload). Raw PUT to the ticket, then complete-upload. */
export function UploadDialog({ open, onOpenChange, folder }: { open: boolean; onOpenChange: (o: boolean) => void; folder: FolderOut | null }) {
  const upload = useUploadDocument();
  const input = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [target, setTarget] = useState<FolderOut | null>(folder);
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const dest = target ?? folder;

  const add = (files: FileList | File[]) => {
    setRows((r) => [...r, ...Array.from(files).map((file): Row => {
      const err = validateFile(file, { types: ALLOWED_MIME });
      return err ? { file, pct: 0, state: "error", error: err } : { file, pct: 0, state: "queued" };
    })]);
  };
  const patch = (i: number, p: Partial<Row>) => setRows((r) => r.map((x, j) => (j === i ? { ...x, ...p } : x)));
  const start = async () => {
    if (!dest) return;
    setBusy(true);
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i]!;
      if (row.state !== "queued") continue;
      patch(i, { state: "uploading" });
      try {
        await upload.mutateAsync({ file: row.file, onProgress: (pct) => patch(i, { pct }), meta: { folder_id: dest.id, title: titleFromFile(row.file.name), source_type: "FILE_UPLOAD" } });
        patch(i, { state: "done", pct: 100 });
      } catch (e) {
        patch(i, { state: "error", error: describeError(e) });
      }
    }
    setBusy(false);
  };
  const close = (o: boolean) => {
    if (busy) return;
    if (!o) setRows([]);
    onOpenChange(o);
  };
  const queued = rows.filter((r) => r.state === "queued").length;
  const done = rows.length > 0 && rows.every((r) => r.state === "done" || r.state === "error");
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent size="lg" title="Upload documents" description={dest ? `Into ${dest.name}` : "Choose a folder first"}
        footer={<>
          <Button onClick={() => setPicking(true)} disabled={busy}>Change folder</Button>
          {done ? <Button variant="primary" onClick={() => close(false)}>Done</Button>
            : <Button variant="primary" disabled={!dest || queued === 0} loading={busy} onClick={() => void start()}>Upload {queued || ""} file{queued === 1 ? "" : "s"}</Button>}
        </>}>
        <div className="flex flex-col gap-3">
          {dest?.is_system_locked && !dest.month_date && dest.child_count > 0 ? <Hint tone="sky">Tip: files usually go into a month’s sub-folder such as Bills & Vouchers.</Hint> : null}
          <input ref={input} type="file" multiple className="sr-only" aria-label="Choose files" accept={ALLOWED_MIME.join(",")} onChange={(e) => { if (e.target.files) add(e.target.files); e.target.value = ""; }} />
          <button type="button" onClick={() => input.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}
            className={cn("flex flex-col items-center gap-1.5 rounded-xl border border-dashed px-4 py-8 text-[13px] text-fg-muted", drag ? "border-primary bg-primary-tint" : "border-line-strong bg-canvas hover:bg-subtle")}>
            <FileUp className="size-6" aria-hidden />
            Drop files here or click to choose · PDF, images, Word, Excel, CSV · up to 50 MB each
          </button>
          {rows.length ? (
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {rows.map((r, i) => (
                <li key={`${r.file.name}-${i}`} className="flex items-center gap-3 rounded-lg border border-line px-3 py-2 text-[12.5px]">
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate font-medium text-fg">{r.file.name}</span>
                    <span className={cn("text-[11.5px]", r.state === "error" ? "text-danger-text" : "text-fg-muted")}>{r.error ?? formatBytes(r.file.size)}</span>
                  </span>
                  {r.state === "uploading" ? (
                    <span className="h-1.5 w-24 rounded bg-line"><span className="block h-1.5 rounded bg-primary" style={{ width: `${r.pct}%` }} /></span>
                  ) : r.state === "done" ? <CheckCircle2 className="size-4 text-success" aria-label="Uploaded" />
                    : r.state === "error" ? <XCircle className="size-4 text-danger" aria-label="Failed" />
                    : <Button size="sm" variant="ghost" onClick={() => setRows((x) => x.filter((_, j) => j !== i))}>Remove</Button>}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <FolderPickerDialog open={picking} onOpenChange={setPicking} title="Upload into…" onPick={(f) => { setTarget(f); setPicking(false); }} />
      </DialogContent>
    </Dialog>
  );
}
