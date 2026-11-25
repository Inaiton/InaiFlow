"use client";

import { Pencil, Plus, Split, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, ConfirmDialog, DataTable, DecimalInput, Dialog, DialogContent, EmptyState, Field, Input, Meter, NativeSelect, PageHeader, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { cmp, isZero, sub } from "@/core/money";
import { Can } from "@/core/permissions/Can";
import { Amt } from "../components/Amount";
import { QueryState } from "../components/QueryState";
import { MASTERS_NAV, SubNav } from "../components/SubNav";
import { useDialogGuard } from "../components/dialog-guard";
import { useAccHref } from "../lib/api-base";
import { percentOf } from "../lib/format";
import { useCostCentres, useDeleteCostCentre, useSaveCostCentre } from "./api";

type CC = Schemas["CostCentreOut"];

function CcDialog({ cc, all, onClose }: { cc: CC | null; all: CC[]; onClose: () => void }) {
  useDialogGuard();
  const save = useSaveCostCentre();
  const [f, setF] = useState({ category_name: cc?.category_name ?? "Primary Cost Category", name: cc?.name ?? "", parent_id: cc?.parent_id ?? "", budget_amount: cc?.budget_amount ?? "" });
  const submit = async () => { await save.mutateAsync({ id: cc?.id, body: { category_name: f.category_name, name: f.name, parent_id: f.parent_id || null, budget_amount: f.budget_amount || null } }); onClose(); };
  return (
    <DialogContent title={cc ? "Alter cost centre" : "Create cost centre"} size="sm"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!f.name.trim()} loading={save.isPending} onClick={() => void submit()}>Save</Button></>}>
      <div className="flex flex-col gap-3">
        <Field label="Name" required><Input autoFocus value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Category"><Input value={f.category_name} onChange={(e) => setF({ ...f, category_name: e.target.value })} /></Field>
        <Field label="Under"><NativeSelect value={f.parent_id} onChange={(e) => setF({ ...f, parent_id: e.target.value })}><option value="">Primary</option>{all.filter((c) => c.id !== cc?.id).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</NativeSelect></Field>
        <Field label="Budget (FY)"><DecimalInput value={f.budget_amount} onValueChange={(v) => setF({ ...f, budget_amount: v ?? "" })} prefix="₹" /></Field>
      </div>
    </DialogContent>
  );
}

/** /accounts/masters/cost-centres — categories, cost centres (incl. period runs) and budget vs actual. */
export function CostCentresPage() {
  const href = useAccHref();
  const q = useCostCentres();
  const del = useDeleteCostCentre();
  const [edit, setEdit] = useState<CC | "new" | null>(null);
  const [remove, setRemove] = useState<CC | null>(null);
  const cols: ColumnDef<CC, unknown>[] = [
    { accessorKey: "name", header: "Cost centre", cell: ({ row: { original: c } }) => <span className="flex items-center gap-2 font-medium text-fg">{c.name}{c.linked_period_run_id ? <Badge tone="indigo">Period run</Badge> : null}</span> },
    { accessorKey: "category_name", header: "Category" },
    { accessorKey: "budget_amount", header: "Budget", meta: { align: "right" }, cell: ({ getValue }) => (getValue() ? <Amt v={getValue() as string} /> : "—") },
    { accessorKey: "actual_amount", header: "Actual", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { id: "var", header: "Variance", meta: { align: "right" }, cell: ({ row: { original: c } }) => c.budget_amount ? <Amt v={sub(c.budget_amount, c.actual_amount)} /> : "—" },
    { id: "use", header: "Used", cell: ({ row: { original: c } }) => c.budget_amount && !isZero(c.budget_amount) ? (
      <div className="w-28"><Meter value={Math.min(100, percentOf(c.actual_amount, c.budget_amount))} max={100} tone={cmp(c.actual_amount, c.budget_amount) > 0 ? "danger" : "teal"} /></div>
    ) : null },
    { id: "act", header: "", cell: ({ row: { original: c } }) => (
      <Can permission="accounts.ledgers_groups" level="WRITE">
        <span className="flex justify-end gap-0.5">
          <Button size="icon-sm" variant="ghost" aria-label="Alter" onClick={(e) => { e.stopPropagation(); setEdit(c); }}><Pencil /></Button>
          {!c.linked_period_run_id ? <Can permission="accounts.ledgers_groups" level="FULL"><Button size="icon-sm" variant="ghost" aria-label="Delete" onClick={(e) => { e.stopPropagation(); setRemove(c); }}><Trash2 /></Button></Can> : null}
        </span>
      </Can>
    ) },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Masters", href: href("/masters") }, { label: "Cost centres" }]} title="Cost centres & budgets"
        description="Period runs from Operations appear here automatically"
        actions={<Can permission="accounts.ledgers_groups" level="WRITE"><Button variant="primary" onClick={() => setEdit("new")}><Plus />New cost centre</Button></Can>} />
      <SubNav items={MASTERS_NAV} />
      <Card padded={false}>
        <QueryState q={q}>{(list) => <DataTable columns={cols} data={list} getRowId={(c) => c.id} aria-label="Cost centres" empty={<EmptyState icon={Split} title="No cost centres yet" description="Create one, or launch a period run in Operations." />} />}</QueryState>
      </Card>
      <Dialog open={Boolean(edit)} onOpenChange={(o) => !o && setEdit(null)}>{edit ? <CcDialog cc={edit === "new" ? null : edit} all={q.data ?? []} onClose={() => setEdit(null)} /> : null}</Dialog>
      <ConfirmDialog open={Boolean(remove)} onOpenChange={(o) => !o && setRemove(null)} title={`Delete ${remove?.name}?`} destructive confirmLabel="Delete" loading={del.isPending}
        onConfirm={async () => { if (remove) await del.mutateAsync(remove.id); setRemove(null); }} />
    </>
  );
}
