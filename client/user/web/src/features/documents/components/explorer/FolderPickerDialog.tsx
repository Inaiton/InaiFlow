"use client";

import { useState } from "react";
import { Button, Dialog, DialogContent } from "@/components/ui";
import type { FolderOut } from "../../api/folders";
import { FolderTree } from "./FolderTree";

/** Choose a destination folder (move / save-to). */
export function FolderPickerDialog({ open, onOpenChange, title, confirmLabel = "Choose", disabledIds, onPick, loading }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; confirmLabel?: string; disabledIds?: string[]; onPick: (f: FolderOut) => void | Promise<void>; loading?: boolean;
}) {
  const [sel, setSel] = useState<FolderOut | null>(null);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} description={sel ? `Into: ${sel.name}` : "Pick a folder"}
        footer={<><Button onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="primary" disabled={!sel} loading={loading} onClick={() => sel && void onPick(sel)}>{confirmLabel}</Button></>}>
        <div className="max-h-[50vh] overflow-y-auto">
          <FolderTree selectedId={sel?.id ?? null} onSelect={setSel} disabledIds={disabledIds} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
