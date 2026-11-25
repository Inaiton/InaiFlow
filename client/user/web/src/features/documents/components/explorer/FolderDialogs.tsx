"use client";

import { useState } from "react";
import { Button, ConfirmDialog, Dialog, DialogContent, Field, Input } from "@/components/ui";
import { useCreateFolder, useDeleteFolder, useUpdateFolder, type FolderOut } from "../../api/folders";
import { FolderPickerDialog } from "./FolderPickerDialog";

export type FolderDialog = "new" | "rename" | "move" | "delete" | null;

/** New / rename / move / delete folder. System-locked folders never reach rename/move/delete (buttons disabled). */
export function FolderDialogs({ dialog, folder, onClose, onDeleted }: { dialog: FolderDialog; folder: FolderOut | null; onClose: () => void; onDeleted: () => void }) {
  const create = useCreateFolder();
  const update = useUpdateFolder();
  const del = useDeleteFolder();
  return (
    <>
      {dialog === "new" && folder ? (
        <NameDialog title={`New folder in ${folder.name}`} initial="" label="Create folder" loading={create.isPending} onClose={onClose}
          onSave={async (name) => { await create.mutateAsync({ parent_folder_id: folder.id, name }); onClose(); }} />
      ) : null}
      {dialog === "rename" && folder ? (
        <NameDialog title="Rename folder" initial={folder.name} label="Rename" loading={update.isPending} onClose={onClose}
          onSave={async (name) => { await update.mutateAsync({ id: folder.id, body: { name } }); onClose(); }} />
      ) : null}
      <FolderPickerDialog open={dialog === "move" && Boolean(folder)} onOpenChange={(o) => !o && onClose()} title={`Move “${folder?.name ?? ""}” to…`} confirmLabel="Move here"
        disabledIds={folder ? [folder.id] : []} loading={update.isPending}
        onPick={async (to) => { if (folder) await update.mutateAsync({ id: folder.id, body: { parent_folder_id: to.id } }); onClose(); }} />
      <ConfirmDialog open={dialog === "delete" && Boolean(folder)} onOpenChange={(o) => !o && onClose()} title={`Delete “${folder?.name ?? ""}”?`}
        description="Only empty folders can be deleted." destructive confirmLabel="Delete folder" loading={del.isPending}
        onConfirm={async () => { if (folder) await del.mutateAsync(folder.id); onClose(); onDeleted(); }} />
    </>
  );
}

function NameDialog({ title, initial, label, loading, onClose, onSave }: { title: string; initial: string; label: string; loading: boolean; onClose: () => void; onSave: (name: string) => Promise<void> }) {
  const [name, setName] = useState(initial);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm" title={title}
        footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!name.trim() || name.trim() === initial} loading={loading} onClick={() => void onSave(name.trim())}>{label}</Button></>}>
        <Field label="Folder name" required><Input autoFocus value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) void onSave(name.trim()); }} /></Field>
      </DialogContent>
    </Dialog>
  );
}
