"use client";

import { Camera, FolderPlus, Lock, MoreHorizontal, Search, Upload } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  Button, Card, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, EmptyState, ErrorState, Input, NativeSelect, PageHeader, Segmented, Skeleton,
} from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { useCan } from "@/core/permissions/Can";
import { useDocSearch, useDocuments, type ApprovalStatus } from "../../api/documents";
import { useFolder, useFolderPath, useFolders, type FolderOut } from "../../api/folders";
import { useDocsPath } from "../../paths";
import { DocIcon, DocumentGrid } from "./DocumentGrid";
import { FolderDialogs, type FolderDialog } from "./FolderDialogs";
import { FolderTree } from "./FolderTree";
import { Inspector } from "./Inspector";
import { UploadDialog } from "./UploadDialog";

/** /documents — FY/month vault explorer (design Doc-Explorer / Doc-Search). State lives in the URL. */
export function ExplorerPage() {
  const d = useDocsPath();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const folderId = params.get("folder");
  const docId = params.get("doc");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [status, setStatus] = useState<ApprovalStatus | "">("");
  const [upload, setUpload] = useState(params.get("upload") === "1");
  const [dialog, setDialog] = useState<FolderDialog>(null);
  const canUpload = useCan("documents.capture_upload", "WRITE");
  const canDeleteFolder = useCan("documents.explorer", "FULL");
  const folder = useFolder(folderId);
  const path = useFolderPath(folderId);
  const kids = useFolders(folderId);
  const docs = useDocuments({ folder_id: folderId ?? undefined, approval_status: status || undefined, limit: 100, offset: 0 }, Boolean(folderId));
  const search = useDocSearch(q);
  const searching = q.trim().length >= 2;

  const nav = (next: Record<string, string | null>) => {
    const sp = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v) sp.set(k, v);
      else sp.delete(k);
    }
    sp.delete("upload");
    router.replace(`${pathname}?${sp.toString()}`, { scroll: false });
  };
  const openFolder = (f: FolderOut | null) => { setQ(""); nav({ folder: f?.id ?? null, doc: null }); };
  const f = folder.data;
  const locked = Boolean(f?.is_system_locked);
  const crumbs = [{ label: "Documents", href: d() }, ...(path.data ?? []).map((p) => ({ label: p.name, href: d(`?folder=${p.id}`) }))];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        crumbs={crumbs}
        title={f?.name ?? "Documents"}
        description={f ? (locked ? "System folder · created automatically, can’t be renamed or deleted" : `${f.document_count} files`) : "Bills, run records, payroll and ISO documents — filed by financial year and month"}
        actions={canUpload ? (
          <>
            <Button asChild><Link href={d(`/scan${folderId ? `?folder=${folderId}` : ""}`)}><Camera /> Scan</Link></Button>
            <Button variant="primary" onClick={() => setUpload(true)}><Upload /> Upload</Button>
          </>
        ) : null}
      />
      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <Card className="max-h-[75vh] overflow-y-auto" padded>
          <FolderTree selectedId={folderId} onSelect={openFolder} expandPath={(path.data ?? []).map((p) => p.id)} />
        </Card>
        <Card>
          <div className="flex flex-wrap items-center gap-2">
            <Input className="max-w-sm" prefix={<Search className="size-4" />} placeholder="Search all documents (title, number, text)" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search documents" />
            {!searching && folderId ? (
              <NativeSelect className="w-40" aria-label="Approval status" value={status} onChange={(e) => setStatus(e.target.value as ApprovalStatus | "")}>
                <option value="">Any status</option><option value="DRAFT">Draft</option><option value="UNDER_REVIEW">Under review</option><option value="APPROVED">Approved</option><option value="OBSOLETE">Obsolete</option>
              </NativeSelect>
            ) : null}
            <span className="flex-1" />
            {f && canUpload ? <Button size="sm" onClick={() => setDialog("new")}><FolderPlus /> New folder</Button> : null}
            {f ? (
              locked ? <span className="flex items-center gap-1 text-xs text-fg-muted"><Lock className="size-3" /> Locked</span> : (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild><Button size="icon-sm" aria-label="Folder actions"><MoreHorizontal /></Button></DropdownMenuTrigger>
                  <DropdownMenuContent>
                    {canUpload ? <DropdownMenuItem onSelect={() => setDialog("rename")}>Rename</DropdownMenuItem> : null}
                    {canUpload ? <DropdownMenuItem onSelect={() => setDialog("move")}>Move</DropdownMenuItem> : null}
                    {canDeleteFolder ? <DropdownMenuItem destructive onSelect={() => setDialog("delete")}>Delete</DropdownMenuItem> : null}
                  </DropdownMenuContent>
                </DropdownMenu>
              )
            ) : null}
            <Segmented aria-label="View" value={view} onChange={setView} options={[{ value: "grid", label: "Grid" }, { value: "list", label: "List" }]} />
          </div>
          {searching ? (
            !search.data ? <Skeleton className="h-40" /> : search.data.length === 0 ? <EmptyState icon={Search} title="No matches" description="Try a document number, supplier name or part name." /> : (
              <ul className="m-0 flex list-none flex-col p-0">
                {search.data.map((h) => (
                  <li key={h.document.id}><button type="button" onClick={() => nav({ doc: h.document.id })} className="flex w-full items-start gap-3 border-b border-line px-2 py-2.5 text-left hover:bg-canvas">
                    <DocIcon mime={h.document.file_mime_type} />
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-[13px] font-semibold text-fg">{h.document.title}</span>
                      <span className="truncate text-xs text-fg-muted">{h.folder_path.join(" / ")}</span>
                      {h.snippet ? <span className="line-clamp-2 text-xs text-fg-2">{h.snippet}</span> : null}
                    </span>
                  </button></li>
                ))}
              </ul>
            )
          ) : kids.isError ? <ErrorState message={describeError(kids.error)} onRetry={() => void kids.refetch()} />
            : !kids.data || (folderId && !docs.data) ? <Skeleton className="h-40" />
            : kids.data.length + (docs.data?.items.length ?? 0) === 0 ? (
              <EmptyState title="This folder is empty" description={canUpload ? "Upload files, scan a paper document or create a report here." : undefined}
                action={canUpload && folderId ? <Button variant="primary" onClick={() => setUpload(true)}><Upload /> Upload</Button> : undefined} />
            ) : (
              <DocumentGrid folders={kids.data} docs={docs.data?.items ?? []} view={view} onFolder={openFolder} onDoc={(x) => nav({ doc: x.id })} />
            )}
        </Card>
      </div>
      <UploadDialog key={folderId ?? "root"} open={upload} onOpenChange={setUpload} folder={f ?? null} />
      <FolderDialogs dialog={dialog} folder={f ?? null} onClose={() => setDialog(null)} onDeleted={() => openFolder(null)} />
      <Inspector docId={docId} onClose={() => nav({ doc: null })} onOpenDoc={(id) => nav({ doc: id })} />
    </div>
  );
}
