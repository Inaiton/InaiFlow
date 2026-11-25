"use client";

import { ChevronRight, Folder, FolderLock, Library } from "lucide-react";
import { useState } from "react";
import { Skeleton } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useFolders, type FolderOut } from "../../api/folders";

/** Lazy folder tree: each level loads `GET /documents/folders?parent_id=` when expanded. */
export function FolderTree({ selectedId, onSelect, expandPath = [], disabledIds = [] }: {
  selectedId: string | null; onSelect: (f: FolderOut | null) => void; expandPath?: string[]; disabledIds?: string[];
}) {
  const roots = useFolders(null);
  return (
    <nav aria-label="Folders" className="flex flex-col gap-0.5 text-[13px]">
      <button type="button" onClick={() => onSelect(null)} className={cn("rounded-lg px-2 py-1.5 text-left font-medium", selectedId === null ? "bg-primary-tint text-primary-text" : "text-fg-2 hover:bg-subtle")}>
        All folders
      </button>
      {!roots.data ? <Skeleton className="h-24" /> : (
        <ul role="tree" className="m-0 flex list-none flex-col p-0">
          {roots.data.map((f) => <TreeNode key={f.id} folder={f} depth={0} selectedId={selectedId} onSelect={onSelect} expandPath={expandPath} disabledIds={disabledIds} />)}
        </ul>
      )}
    </nav>
  );
}

function TreeNode({ folder, depth, selectedId, onSelect, expandPath, disabledIds }: {
  folder: FolderOut; depth: number; selectedId: string | null; onSelect: (f: FolderOut) => void; expandPath: string[]; disabledIds: string[];
}) {
  const [open, setOpen] = useState(expandPath.includes(folder.id));
  const kids = useFolders(folder.id, open && folder.child_count > 0);
  const active = selectedId === folder.id;
  const disabled = disabledIds.includes(folder.id);
  const Icon = folder.system_kind === "MASTER_LIBRARY" ? Library : folder.is_system_locked ? FolderLock : Folder;
  return (
    <li role="treeitem" aria-expanded={folder.child_count ? open : undefined} aria-selected={active}>
      <div className={cn("flex items-center gap-1 rounded-lg pr-2", active ? "bg-primary-tint" : "hover:bg-subtle")} style={{ paddingLeft: depth * 14 }}>
        <button type="button" aria-label={open ? "Collapse" : "Expand"} onClick={() => setOpen(!open)} className={cn("grid size-6 place-items-center text-fg-muted", !folder.child_count && "invisible")}>
          <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        </button>
        <button type="button" disabled={disabled} onClick={() => { onSelect(folder); if (folder.child_count) setOpen(true); }}
          className={cn("flex min-w-0 flex-1 items-center gap-1.5 py-1.5 text-left disabled:opacity-40", active ? "font-semibold text-primary-text" : "text-fg-2")}>
          <Icon className={cn("size-4 flex-none", folder.is_system_locked ? "text-fg-muted" : "text-sky-text")} aria-hidden />
          <span className="truncate">{folder.name}</span>
          {folder.document_count ? <span className="ml-auto text-[11px] text-fg-faint">{folder.document_count}</span> : null}
        </button>
      </div>
      {open && folder.child_count ? (
        kids.data ? (
          <ul role="group" className="m-0 flex list-none flex-col p-0">
            {kids.data.map((k) => <TreeNode key={k.id} folder={k} depth={depth + 1} selectedId={selectedId} onSelect={onSelect} expandPath={expandPath} disabledIds={disabledIds} />)}
          </ul>
        ) : <Skeleton className="ml-6 h-6" />
      ) : null}
    </li>
  );
}
