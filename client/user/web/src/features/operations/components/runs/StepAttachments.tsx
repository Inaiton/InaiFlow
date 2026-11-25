"use client";

import { Camera, FileText, Paperclip, Upload } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button, Skeleton } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { useCan } from "@/core/permissions/Can";
import { validateFile } from "@/core/upload";
import { ALLOWED_MIME, titleFromFile, useDocsPath, useDocuments, useUploadDocument } from "@/features/documents/public";

/** Files and reports linked to a run step (uploads go into the run’s locked folder). */
export function StepAttachments({ run, step, reportTemplateId }: { run: Schemas["RunOut"]; step: Schemas["StepOut"]; reportTemplateId: string | null }) {
  const d = useDocsPath();
  const canRead = useCan("documents.explorer", "READ");
  const canUpload = useCan("documents.capture_upload", "WRITE");
  const canEdit = useCan("documents.editor", "WRITE");
  const docs = useDocuments({ linked_step_id: step.id, limit: 50, offset: 0 }, canRead);
  const upload = useUploadDocument();
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const ctx = `run=${run.id}&step=${step.id}`;

  const onFiles = async (files: FileList | null) => {
    if (!files || !run.doc_folder_id) return;
    for (const file of Array.from(files)) {
      const err = validateFile(file, { types: ALLOWED_MIME });
      if (err) { toast.error(`${file.name}: ${err}`); continue; }
      try {
        setProgress(0);
        await upload.mutateAsync({ file, onProgress: setProgress, meta: { folder_id: run.doc_folder_id, title: titleFromFile(file.name), source_type: "FILE_UPLOAD", linked_period_run_id: run.id, linked_step_id: step.id } });
        toast.success(`${file.name} attached`);
      } catch (e) {
        toast.error(describeError(e));
      }
    }
    setProgress(null);
  };

  return (
    <div className="flex flex-col gap-2.5">
      {!canRead ? <p className="m-0 text-xs text-fg-muted">You don’t have access to documents.</p> : !docs.data ? <Skeleton className="h-10" /> : docs.data.items.length === 0 ? (
        <p className="m-0 text-xs text-fg-muted">Nothing attached yet.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {docs.data.items.map((doc) => (
            <li key={doc.id}>
              <Link href={doc.file_mime_type ? d(`?doc=${doc.id}&folder=${doc.folder_id}`) : d(`/editor/${doc.id}`)} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[12.5px] no-underline hover:bg-subtle">
                {doc.file_mime_type ? <Paperclip className="size-3.5 text-fg-muted" /> : <FileText className="size-3.5 text-sky-text" />}
                <span className="flex-1 truncate text-fg">{doc.title}</span>
                <span className="text-[11px] text-fg-muted">{doc.approval_status === "DRAFT" ? "Draft" : doc.approval_status.replace("_", " ").toLowerCase()}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <input ref={input} type="file" multiple className="sr-only" aria-label="Attach files" accept={ALLOWED_MIME.join(",")} onChange={(e) => { void onFiles(e.target.files); e.target.value = ""; }} />
      <div className="flex flex-wrap gap-2">
        {canUpload && run.doc_folder_id ? (
          <>
            <Button size="sm" loading={progress !== null} onClick={() => input.current?.click()}><Upload /> {progress !== null ? `${progress}%` : "Attach file"}</Button>
            <Button asChild size="sm"><Link href={d(`/scan?${ctx}&folder=${run.doc_folder_id}`)}><Camera /> Scan</Link></Button>
          </>
        ) : null}
        {canEdit ? <Button asChild size="sm"><Link href={d(`/reports/new?${ctx}${reportTemplateId ? `&template=${reportTemplateId}` : ""}`)}><FileText /> Step report</Link></Button> : null}
      </div>
    </div>
  );
}
