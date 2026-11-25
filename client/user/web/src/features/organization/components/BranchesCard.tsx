"use client";

import { MoreHorizontal, Plus } from "lucide-react";
import { useState } from "react";
import { Controller } from "react-hook-form";
import { z } from "zod";
import type { Schemas } from "@/core/api/types";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { Can } from "@/core/permissions/Can";
import {
  Badge, Button, Card, CheckboxRow, ConfirmDialog, DataTable, Dialog, DialogContent, DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuTrigger, EmptyState, Field, Input, Textarea, type ColumnDef,
} from "@/components/ui";
import { GSTIN_RE } from "@/features/org-create/schema";
import { StateSelect } from "@/features/org-create/components/StateSelect";
import { useBranches, useDeleteBranch, useSaveBranch } from "../api";

type Branch = Schemas["BranchOut"];
const schema = z.object({
  name: z.string().trim().min(2, "Enter a name").max(120),
  address: z.string().trim().max(300),
  state_code: z.string(),
  gstin: z.string().trim().toUpperCase().refine((v) => v === "" || GSTIN_RE.test(v), "Invalid GSTIN"),
  is_head_office: z.boolean(),
});

function BranchDialog({ branch, open, onOpenChange }: { branch: Branch | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  const save = useSaveBranch();
  const form = useZodForm(schema, {
    values: { name: branch?.name ?? "", address: branch?.address ?? "", state_code: branch?.state_code ?? "", gstin: branch?.gstin ?? "", is_head_office: branch?.is_head_office ?? false },
  });
  const { errors } = form.formState;
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await save.mutateAsync({ id: branch?.id, body: { name: v.name, address: v.address || null, state_code: v.state_code || null, gstin: v.gstin || null, is_head_office: v.is_head_office } });
      onOpenChange(false);
    } catch (e) {
      applyServerErrors(form, e);
    }
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={branch ? "Edit branch" : "Add branch"} description="Branches carry their own address and can have separate GSTINs"
        footer={<><Button onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => void onSubmit()}>{branch ? "Save" : "Add branch"}</Button></>}>
        <form onSubmit={onSubmit} className="flex flex-col gap-3.5" noValidate>
          <Field label="Name" error={errors.name?.message} required><Input autoFocus {...form.register("name")} /></Field>
          <Field label="State"><Controller control={form.control} name="state_code" render={({ field }) => <StateSelect value={field.value} onChange={field.onChange} />} /></Field>
          <Field label="GSTIN" hint="Same state → same GSTIN; other state → new registration" error={errors.gstin?.message}><Input {...form.register("gstin")} /></Field>
          <Field label="Address"><Textarea rows={2} {...form.register("address")} /></Field>
          <CheckboxRow label="Head office" checked={form.watch("is_head_office")} onCheckedChange={(v) => form.setValue("is_head_office", v, { shouldDirty: true })} />
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function BranchesCard() {
  const branches = useBranches();
  const del = useDeleteBranch();
  const [editing, setEditing] = useState<Branch | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState<Branch | null>(null);
  const columns: ColumnDef<Branch, unknown>[] = [
    { accessorKey: "name", header: "Branch", cell: ({ row }) => <span className="flex items-center gap-2 font-semibold text-fg">{row.original.name}{row.original.is_head_office ? <Badge tone="accent">Head office</Badge> : null}</span> },
    { accessorKey: "state_code", header: "State", cell: ({ getValue }) => (getValue() as string | null) ?? "—" },
    { accessorKey: "gstin", header: "GSTIN", cell: ({ getValue }) => <span className="font-mono text-xs">{(getValue() as string | null) ?? "—"}</span> },
    { accessorKey: "address", header: "Address", cell: ({ getValue }) => <span className="line-clamp-1">{(getValue() as string | null) ?? "—"}</span> },
    {
      id: "actions", header: "", meta: { align: "right" }, cell: ({ row }) => (
        <Can permission="organization.profile" level="FULL">
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button size="icon-sm" variant="ghost" aria-label={`Actions for ${row.original.name}`}><MoreHorizontal /></Button></DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onSelect={() => { setEditing(row.original); setDialogOpen(true); }}>Edit</DropdownMenuItem>
              <DropdownMenuItem destructive onSelect={() => setDeleting(row.original)}>Delete</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </Can>
      ),
    },
  ];
  return (
    <Card title="Branches & locations" description="Factories, offices and warehouses"
      actions={<Can permission="organization.profile" level="FULL"><Button size="sm" onClick={() => { setEditing(null); setDialogOpen(true); }}><Plus /> Add branch</Button></Can>}>
      <DataTable columns={columns} data={branches.data} loading={branches.isPending} aria-label="Branches"
        empty={<EmptyState title="No branches yet" description="Add factory units or offices — each can carry its own GSTIN." />} />
      <BranchDialog branch={editing} open={dialogOpen} onOpenChange={setDialogOpen} />
      <ConfirmDialog open={deleting !== null} onOpenChange={(o) => !o && setDeleting(null)} title={`Delete ${deleting?.name ?? "branch"}?`} destructive confirmLabel="Delete"
        loading={del.isPending} onConfirm={() => { if (deleting) del.mutate(deleting.id, { onSuccess: () => setDeleting(null) }); }} />
    </Card>
  );
}
