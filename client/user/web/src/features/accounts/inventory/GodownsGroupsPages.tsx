"use client";

import { Pencil, Plus, Trash2, Warehouse } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, ConfirmDialog, DataTable, Dialog, DialogContent, EmptyState, Field, Input, NativeSelect, PageHeader, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { Can } from "@/core/permissions/Can";
import { QueryState } from "../components/QueryState";
import { INVENTORY_NAV, SubNav } from "../components/SubNav";
import { useDialogGuard } from "../components/dialog-guard";
import { useAccHref } from "../lib/api-base";
import { humanize } from "../lib/format";
import { useDeleteGodown, useDeleteStockGroup, useGodowns, useSaveGodown, useSaveStockGroup, useStockGroups } from "./api";

type Godown = Schemas["GodownOut"];
type SGroup = Schemas["StockGroupOut"];
const GODOWN_TYPES = ["INTERNAL", "WIP", "FG", "SCRAP", "JOB_WORKER"];

function NameDialog({ title, initial, parents, types, onSave, onClose, loading }: {
  title: string; initial: { name: string; parent: string; type?: string }; parents: { id: string; name: string }[]; types?: string[];
  onSave: (v: { name: string; parent: string; type: string }) => Promise<unknown>; onClose: () => void; loading: boolean;
}) {
  useDialogGuard();
  const [f, setF] = useState({ name: initial.name, parent: initial.parent, type: initial.type ?? "INTERNAL" });
  const submit = async () => { await onSave(f); onClose(); };
  return (
    <DialogContent title={title} size="sm" footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!f.name.trim()} loading={loading} onClick={() => void submit()}>Save</Button></>}>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <Field label="Name" required><Input autoFocus value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Under"><NativeSelect value={f.parent} onChange={(e) => setF({ ...f, parent: e.target.value })}><option value="">Primary</option>{parents.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</NativeSelect></Field>
        {types ? <Field label="Type"><NativeSelect value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{types.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</NativeSelect></Field> : null}
      </form>
    </DialogContent>
  );
}

/** /accounts/inventory/godowns */
export function GodownsPage() {
  const href = useAccHref();
  const q = useGodowns();
  const save = useSaveGodown();
  const del = useDeleteGodown();
  const [edit, setEdit] = useState<Godown | "new" | null>(null);
  const [remove, setRemove] = useState<Godown | null>(null);
  const names = new Map((q.data ?? []).map((g) => [g.id, g.name]));
  const cols: ColumnDef<Godown, unknown>[] = [
    { accessorKey: "name", header: "Godown", cell: ({ row: { original: g } }) => <span className="flex items-center gap-2 font-medium text-fg">{g.name}{g.is_system ? <Badge>System</Badge> : null}</span> },
    { accessorKey: "godown_type", header: "Type", cell: ({ getValue }) => humanize(getValue() as string) },
    { id: "parent", header: "Under", cell: ({ row: { original: g } }) => (g.parent_godown_id ? names.get(g.parent_godown_id) : "Primary") },
    { id: "act", header: "", cell: ({ row: { original: g } }) => (
      <Can permission="accounts.inventory_masters" level="WRITE"><span className="flex justify-end gap-0.5">
        <Button size="icon-sm" variant="ghost" aria-label={`Alter ${g.name}`} onClick={() => setEdit(g)}><Pencil /></Button>
        {!g.is_system ? <Can permission="accounts.inventory_masters" level="FULL"><Button size="icon-sm" variant="ghost" aria-label={`Delete ${g.name}`} onClick={() => setRemove(g)}><Trash2 /></Button></Can> : null}
      </span></Can>
    ) },
  ];
  const cur = edit === "new" ? null : edit;
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Inventory", href: href("/inventory") }, { label: "Godowns" }]} title="Godowns" description="Stores, WIP, finished goods, scrap yards and job workers"
        actions={<Can permission="accounts.inventory_masters" level="WRITE"><Button variant="primary" onClick={() => setEdit("new")}><Plus />New godown</Button></Can>} />
      <SubNav items={INVENTORY_NAV} />
      <Card padded={false}><QueryState q={q}>{(list) => <DataTable columns={cols} data={list} getRowId={(g) => g.id} aria-label="Godowns" empty={<EmptyState icon={Warehouse} title="No godowns" />} />}</QueryState></Card>
      <Dialog open={Boolean(edit)} onOpenChange={(o) => !o && setEdit(null)}>
        {edit ? <NameDialog title={cur ? "Alter godown" : "Create godown"} initial={{ name: cur?.name ?? "", parent: cur?.parent_godown_id ?? "", type: cur?.godown_type }} types={GODOWN_TYPES}
          parents={(q.data ?? []).filter((g) => g.id !== cur?.id)} loading={save.isPending} onClose={() => setEdit(null)}
          onSave={(v) => save.mutateAsync({ id: cur?.id, body: { name: v.name, parent_godown_id: v.parent || null, godown_type: v.type } })} /> : null}
      </Dialog>
      <ConfirmDialog open={Boolean(remove)} onOpenChange={(o) => !o && setRemove(null)} title={`Delete ${remove?.name}?`} destructive confirmLabel="Delete" loading={del.isPending}
        onConfirm={async () => { if (remove) await del.mutateAsync(remove.id); setRemove(null); }} />
    </>
  );
}

/** /accounts/inventory/groups */
export function StockGroupsPage() {
  const href = useAccHref();
  const q = useStockGroups();
  const save = useSaveStockGroup();
  const del = useDeleteStockGroup();
  const [edit, setEdit] = useState<SGroup | "new" | null>(null);
  const [remove, setRemove] = useState<SGroup | null>(null);
  const names = new Map((q.data ?? []).map((g) => [g.id, g.name]));
  const cols: ColumnDef<SGroup, unknown>[] = [
    { accessorKey: "name", header: "Stock group", cell: ({ getValue }) => <span className="font-medium text-fg">{getValue() as string}</span> },
    { id: "parent", header: "Under", cell: ({ row: { original: g } }) => (g.parent_id ? names.get(g.parent_id) : "Primary") },
    { id: "act", header: "", cell: ({ row: { original: g } }) => (
      <Can permission="accounts.inventory_masters" level="WRITE"><span className="flex justify-end gap-0.5">
        <Button size="icon-sm" variant="ghost" aria-label={`Alter ${g.name}`} onClick={() => setEdit(g)}><Pencil /></Button>
        <Can permission="accounts.inventory_masters" level="FULL"><Button size="icon-sm" variant="ghost" aria-label={`Delete ${g.name}`} onClick={() => setRemove(g)}><Trash2 /></Button></Can>
      </span></Can>
    ) },
  ];
  const cur = edit === "new" ? null : edit;
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Inventory", href: href("/inventory") }, { label: "Stock groups" }]} title="Stock groups" description="Group items for reports (finished goods, raw material, consumables…)"
        actions={<Can permission="accounts.inventory_masters" level="WRITE"><Button variant="primary" onClick={() => setEdit("new")}><Plus />New stock group</Button></Can>} />
      <SubNav items={INVENTORY_NAV} />
      <Card padded={false}><QueryState q={q}>{(list) => <DataTable columns={cols} data={list} getRowId={(g) => g.id} aria-label="Stock groups" empty={<EmptyState title="No stock groups" />} />}</QueryState></Card>
      <Dialog open={Boolean(edit)} onOpenChange={(o) => !o && setEdit(null)}>
        {edit ? <NameDialog title={cur ? "Alter stock group" : "Create stock group"} initial={{ name: cur?.name ?? "", parent: cur?.parent_id ?? "" }}
          parents={(q.data ?? []).filter((g) => g.id !== cur?.id)} loading={save.isPending} onClose={() => setEdit(null)}
          onSave={(v) => save.mutateAsync({ id: cur?.id, body: { name: v.name, parent_id: v.parent || null } })} /> : null}
      </Dialog>
      <ConfirmDialog open={Boolean(remove)} onOpenChange={(o) => !o && setRemove(null)} title={`Delete ${remove?.name}?`} destructive confirmLabel="Delete" loading={del.isPending}
        onConfirm={async () => { if (remove) await del.mutateAsync(remove.id); setRemove(null); }} />
    </>
  );
}
