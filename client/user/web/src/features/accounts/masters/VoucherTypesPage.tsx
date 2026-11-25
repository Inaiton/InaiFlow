"use client";

import { Hash, Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, DataTable, Dialog, DialogContent, EmptyState, Field, FieldRow, Input, NativeSelect, PageHeader, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { Can } from "@/core/permissions/Can";
import { QueryState } from "../components/QueryState";
import { MASTERS_NAV, SubNav } from "../components/SubNav";
import { useDialogGuard } from "../components/dialog-guard";
import { useAccHref } from "../lib/api-base";
import { VOUCHER_KINDS } from "../lib/voucher-kinds";
import { expectedNumber } from "../vouchers/entry/VoucherHead";
import { useSaveVoucherType, useVoucherTypes } from "./api";

type VT = Schemas["VoucherTypeOut"];

function VtDialog({ vt, onClose }: { vt: VT | null; onClose: () => void }) {
  useDialogGuard();
  const save = useSaveVoucherType();
  const [f, setF] = useState({ name: vt?.name ?? "", base_type: vt?.base_type ?? "SALES", numbering_method: vt?.numbering_method ?? "AUTOMATIC", prefix: vt?.prefix ?? "", suffix: vt?.suffix ?? "", zero_padding: String(vt?.zero_padding ?? 4), next_number: String(vt?.next_number ?? 1) });
  const ok = f.name.trim() && /^\d+$/.test(f.zero_padding) && /^\d+$/.test(f.next_number);
  const preview = expectedNumber({ ...(vt ?? ({} as VT)), prefix: f.prefix, suffix: f.suffix, zero_padding: Number(f.zero_padding) || 0, next_number: Number(f.next_number) || 1 });
  const submit = async () => {
    const body = { name: f.name, base_type: f.base_type, numbering_method: f.numbering_method, prefix: f.prefix, suffix: f.suffix, zero_padding: Number(f.zero_padding), next_number: Number(f.next_number) };
    await save.mutateAsync({ id: vt?.id, body });
    onClose();
  };
  return (
    <DialogContent title={vt ? `Alter ${vt.name}` : "Create voucher type"} description={`Next number preview: ${preview}`} size="md"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!ok} loading={save.isPending} onClick={() => void submit()}>Save</Button></>}>
      <div className="flex flex-col gap-3">
        <FieldRow>
          <Field label="Name" required><Input autoFocus value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field label="Type of voucher"><NativeSelect value={f.base_type} disabled={Boolean(vt)} onChange={(e) => setF({ ...f, base_type: e.target.value })}>{VOUCHER_KINDS.map((k) => <option key={k.base} value={k.base}>{k.label}</option>)}</NativeSelect></Field>
        </FieldRow>
        <FieldRow>
          <Field label="Numbering"><NativeSelect value={f.numbering_method} onChange={(e) => setF({ ...f, numbering_method: e.target.value })}><option value="AUTOMATIC">Automatic</option><option value="MANUAL">Manual</option></NativeSelect></Field>
          <Field label="Next number"><Input inputMode="numeric" value={f.next_number} onChange={(e) => setF({ ...f, next_number: e.target.value })} /></Field>
        </FieldRow>
        <FieldRow>
          <Field label="Prefix"><Input value={f.prefix} onChange={(e) => setF({ ...f, prefix: e.target.value })} placeholder="SI/" /></Field>
          <Field label="Suffix"><Input value={f.suffix} onChange={(e) => setF({ ...f, suffix: e.target.value })} placeholder="/26-27" /></Field>
          <Field label="Zero padding"><Input inputMode="numeric" value={f.zero_padding} onChange={(e) => setF({ ...f, zero_padding: e.target.value })} /></Field>
        </FieldRow>
      </div>
    </DialogContent>
  );
}

/** /accounts/masters/voucher-types — numbering series per voucher type. */
export function VoucherTypesPage() {
  const href = useAccHref();
  const q = useVoucherTypes();
  const [edit, setEdit] = useState<VT | "new" | null>(null);
  const cols: ColumnDef<VT, unknown>[] = [
    { accessorKey: "name", header: "Voucher type", cell: ({ row: { original: v } }) => <span className="flex items-center gap-2 font-medium text-fg">{v.name}{v.is_system ? <Badge>System</Badge> : null}{!v.is_accounting ? <Badge tone="sky">Non-accounting</Badge> : null}</span> },
    { accessorKey: "base_type", header: "Type", cell: ({ getValue }) => VOUCHER_KINDS.find((k) => k.base === getValue())?.label ?? (getValue() as string) },
    { accessorKey: "shortcut", header: "Key", cell: ({ getValue }) => (getValue() ? <Badge tone="indigo">{getValue() as string}</Badge> : "—") },
    { accessorKey: "numbering_method", header: "Numbering" },
    { id: "next", header: "Next no.", cell: ({ row: { original: v } }) => <span className="font-mono text-[12px]">{expectedNumber(v)}</span> },
    { id: "act", header: "", cell: ({ row: { original: v } }) => <Can permission="accounts.vouchers" level="FULL"><Button size="icon-sm" variant="ghost" aria-label={`Alter ${v.name}`} onClick={() => setEdit(v)}><Pencil /></Button></Can> },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Masters", href: href("/masters") }, { label: "Voucher types" }]} title="Voucher types" description="Custom sub-vouchers and numbering series (number is allocated on save)"
        actions={<Can permission="accounts.vouchers" level="FULL"><Button variant="primary" onClick={() => setEdit("new")}><Plus />New voucher type</Button></Can>} />
      <SubNav items={MASTERS_NAV} />
      <Card padded={false}><QueryState q={q}>{(list) => <DataTable columns={cols} data={list} getRowId={(v) => v.id} aria-label="Voucher types" empty={<EmptyState icon={Hash} title="No voucher types" />} />}</QueryState></Card>
      <Dialog open={Boolean(edit)} onOpenChange={(o) => !o && setEdit(null)}>{edit ? <VtDialog vt={edit === "new" ? null : edit} onClose={() => setEdit(null)} /> : null}</Dialog>
    </>
  );
}
