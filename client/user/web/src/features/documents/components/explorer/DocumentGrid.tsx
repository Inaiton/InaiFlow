"use client";

import { FileImage, FileSpreadsheet, FileText, Folder, FolderLock, Lock, ScrollText } from "lucide-react";
import { StatusBadge } from "@/components/ui";
import { formatDate } from "@/core/dates";
import { cn } from "@/lib/utils";
import type { DocumentSummary } from "../../api/documents";
import type { FolderOut } from "../../api/folders";
import { fileKind } from "../../lib/transfer";

const ICONS = { pdf: FileText, image: FileImage, doc: FileText, sheet: FileSpreadsheet, text: FileText, report: ScrollText, other: FileText };

export function DocIcon({ mime, className }: { mime: string | null; className?: string }) {
  const kind = fileKind(mime);
  const Icon = ICONS[kind];
  return <Icon className={cn("size-5", kind === "report" ? "text-violet-text" : kind === "image" ? "text-teal-text" : kind === "pdf" ? "text-danger-text" : "text-sky-text", className)} aria-hidden />;
}

/** Sub-folders + documents of the current folder, as tiles or rows. */
export function DocumentGrid({ folders, docs, view, onFolder, onDoc }: { folders: FolderOut[]; docs: DocumentSummary[]; view: "grid" | "list"; onFolder: (f: FolderOut) => void; onDoc: (d: DocumentSummary) => void }) {
  if (view === "list") {
    return (
      <ul className="m-0 flex list-none flex-col p-0">
        {folders.map((f) => (
          <li key={f.id}><button type="button" onClick={() => onFolder(f)} className="flex w-full items-center gap-3 border-b border-line px-2 py-2 text-left text-[13px] hover:bg-canvas">
            {f.is_system_locked ? <FolderLock className="size-5 text-fg-muted" /> : <Folder className="size-5 text-sky-text" />}
            <span className="flex-1 truncate font-medium text-fg">{f.name}</span>
            <span className="text-xs text-fg-muted">{f.document_count} files</span>
          </button></li>
        ))}
        {docs.map((d) => (
          <li key={d.id}><button type="button" onClick={() => onDoc(d)} className="flex w-full items-center gap-3 border-b border-line px-2 py-2 text-left text-[13px] hover:bg-canvas">
            <DocIcon mime={d.file_mime_type} />
            <span className="flex min-w-0 flex-1 flex-col"><span className="truncate font-medium text-fg">{d.title}</span><span className="truncate text-xs text-fg-muted">{d.iso_doc_number ? `${d.iso_doc_number} · ` : ""}Rev {d.revision_no} · {d.prepared_by_name}</span></span>
            <span className="text-xs text-fg-muted">{formatDate(d.updated_at)}</span>
            <StatusBadge status={d.approval_status} />
          </button></li>
        ))}
      </ul>
    );
  }
  return (
    <ul className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-3 p-0">
      {folders.map((f) => (
        <li key={f.id}><button type="button" onClick={() => onFolder(f)} className="flex h-full w-full flex-col gap-2 rounded-xl border border-line bg-surface px-3 py-3 text-left hover:border-line-strong">
          <span className="flex items-center justify-between">{f.is_system_locked ? <FolderLock className="size-6 text-fg-muted" /> : <Folder className="size-6 text-sky-text" />}{f.is_system_locked ? <Lock className="size-3 text-fg-faint" aria-label="System folder" /> : null}</span>
          <span className="line-clamp-2 text-[13px] font-semibold text-fg">{f.name}</span>
          <span className="text-[11.5px] text-fg-muted">{f.child_count ? `${f.child_count} folders · ` : ""}{f.document_count} files</span>
        </button></li>
      ))}
      {docs.map((d) => (
        <li key={d.id}><button type="button" onClick={() => onDoc(d)} className="flex h-full w-full flex-col gap-2 rounded-xl border border-line bg-surface px-3 py-3 text-left hover:border-line-strong">
          <span className="flex items-center justify-between"><DocIcon mime={d.file_mime_type} className="size-6" /><StatusBadge status={d.approval_status} /></span>
          <span className="line-clamp-2 text-[13px] font-semibold text-fg">{d.title}</span>
          <span className="text-[11.5px] text-fg-muted">Rev {d.revision_no} · {formatDate(d.updated_at)}</span>
        </button></li>
      ))}
    </ul>
  );
}
