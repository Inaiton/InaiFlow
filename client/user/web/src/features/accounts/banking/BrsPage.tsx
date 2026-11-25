"use client";

import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card, DataTable, DatePicker, EmptyState, Field, KeyValue, NativeSelect, PageHeader, Segmented, StatusBadge, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { todayIso } from "@/core/dates";
import { useCan } from "@/core/permissions/Can";
import { Amt, Bal } from "../components/Amount";
import { QueryState } from "../components/QueryState";
import { useAccHref } from "../lib/api-base";
import { accDate, amt, inr } from "../lib/format";
import { useRBar } from "../shell/rbar-context";
import { useImportStatement, useLineAction, useReconciliation, useSetReconDate, useStatementLines } from "./api";

type Entry = Schemas["ReconEntryOut"];
type Line = Schemas["StatementLineOut"];

function StatementLines({ ledgerId, entries }: { ledgerId: string; entries: Entry[] }) {
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const q = useStatementLines(ledgerId, status || undefined, offset);
  const act = useLineAction();
  const canWrite = useCan("accounts.banking", "WRITE");
  const open = entries.filter((e) => !e.bank_reconciliation_date);
  const cols: ColumnDef<Line, unknown>[] = [
    { accessorKey: "txn_date", header: "Date", cell: ({ getValue }) => accDate(getValue() as string) },
    { accessorKey: "description", header: "Description", cell: ({ row: { original: l } }) => <span className="flex flex-col"><span>{l.description}</span>{l.reference ? <span className="text-[11.5px] text-fg-muted">Ref {l.reference}</span> : null}</span> },
    { accessorKey: "debit", header: "Withdrawal", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} blankZero /> },
    { accessorKey: "credit", header: "Deposit", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} blankZero /> },
    { accessorKey: "status", header: "Status", cell: ({ getValue }) => <StatusBadge status={getValue() as string} /> },
    { id: "act", header: "", cell: ({ row: { original: l } }) => !canWrite ? null : l.matched_entry_id ? (
      <Button size="sm" variant="ghost" onClick={() => act.mutate({ lineId: l.id, action: "unmatch" })}>Unmatch</Button>
    ) : (
      <span className="flex gap-1">
        <NativeSelect aria-label="Match to book entry" className="h-8 w-56 text-[12px]" value="" onChange={(e) => e.target.value && act.mutate({ lineId: l.id, action: "match", entryId: e.target.value })}>
          <option value="">Match to…</option>{open.map((e) => <option key={e.entry_id} value={e.entry_id}>{accDate(e.voucher_date)} · {e.voucher_number} · {amt(e.debit !== "0" ? e.debit : e.credit)}</option>)}
        </NativeSelect>
        {l.status !== "IGNORED" ? <Button size="sm" variant="ghost" onClick={() => act.mutate({ lineId: l.id, action: "ignore" })}>Ignore</Button> : null}
      </span>
    ) },
  ];
  return (
    <Card padded={false} title="Bank statement lines" actions={<Segmented value={status} onChange={(v) => { setOffset(0); setStatus(v); }} options={[{ value: "", label: "All" }, { value: "UNMATCHED", label: "Unmatched" }, { value: "MATCHED", label: "Matched" }, { value: "IGNORED", label: "Ignored" }]} />}>
      <QueryState q={q}>{(page) => <DataTable columns={cols} data={page.items} getRowId={(l) => l.id} aria-label="Statement lines" pagination={{ total: page.total, limit: page.limit, offset: page.offset, onOffsetChange: setOffset }} empty={<EmptyState title="No imported lines" description="Import a CSV, OFX or MT940 statement." />} />}</QueryState>
    </Card>
  );
}

/** /accounts/banking/[ledgerId] — bank reconciliation statement (design: Acc-Banking, Acc-B-Import). */
export function BrsPage({ ledgerId }: { ledgerId: string }) {
  const href = useAccHref();
  const [asOf, setAsOf] = useState(todayIso());
  const [show, setShow] = useState("unreconciled");
  const q = useReconciliation(ledgerId, asOf, show);
  const setDate = useSetReconDate();
  const imp = useImportStatement(ledgerId);
  const fileRef = useRef<HTMLInputElement>(null);
  const canWrite = useCan("accounts.banking", "WRITE");
  useRBar([{ id: "import", combo: "alt+o", label: "Import statement", run: () => fileRef.current?.click(), disabled: !canWrite }, { id: "cheques", combo: "alt+q", label: "Cheques", href: href("/banking/cheques") }], "accounts");
  const onFile = async (f: File | undefined) => {
    if (!f) return;
    const r = await imp.mutateAsync(f);
    toast.message(`${r.lines_imported} lines imported (${r.format}) · ${r.auto_matched} auto-matched · ${r.duplicates_skipped} duplicates skipped`);
  };
  const cols: ColumnDef<Entry, unknown>[] = [
    { accessorKey: "voucher_date", header: "Date", cell: ({ getValue }) => accDate(getValue() as string) },
    { accessorKey: "particulars", header: "Particulars", cell: ({ row: { original: e } }) => <span className="flex flex-col"><span className="font-medium text-fg">{e.particulars}</span><span className="text-[11.5px] text-fg-muted">{e.voucher_type} {e.voucher_number}{e.instrument_no ? ` · Inst. ${e.instrument_no}` : ""}</span></span> },
    { accessorKey: "debit", header: "Debit", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} blankZero /> },
    { accessorKey: "credit", header: "Credit", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} blankZero /> },
    { id: "bank", header: "Bank date", cell: ({ row: { original: e } }) => canWrite ? (
      <DatePicker aria-label={`Bank date for ${e.voucher_number}`} className="h-8 w-40" value={e.bank_reconciliation_date} onValueChange={(v) => setDate.mutate({ entryId: e.entry_id, date: v })} />
    ) : accDate(e.bank_reconciliation_date) },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Banking", href: href("/banking") }, { label: "Reconciliation" }]} title="Bank reconciliation"
        description="Set the bank date on each entry, or import the statement and match lines"
        actions={canWrite ? <><input ref={fileRef} type="file" className="sr-only" aria-label="Bank statement file" accept=".csv,.ofx,.sta,.mt940,.txt,text/csv" onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = ""; }} />
          <Button variant="primary" loading={imp.isPending} onClick={() => fileRef.current?.click()}><Upload />Import statement (CSV/OFX/MT940)</Button></> : null} />
      <QueryState q={q} rows={6}>
        {(r) => (
          <>
            <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
              <Card padded={false} title="Book entries" actions={<div className="flex items-end gap-2">
                <Field label="As on"><DatePicker value={asOf} onValueChange={(v) => setAsOf(v ?? todayIso())} className="h-8" /></Field>
                <Segmented value={show} onChange={setShow} options={[{ value: "unreconciled", label: "Unreconciled" }, { value: "reconciled", label: "Reconciled" }, { value: "all", label: "All" }]} />
              </div>}>
                <DataTable columns={cols} data={r.entries} getRowId={(e) => e.entry_id} aria-label="Book entries" empty={<EmptyState title="Everything is reconciled" />} />
              </Card>
              <Card title="Reconciliation summary">
                <KeyValue rows={[
                  ["Balance as per books", <Bal key="b" v={r.balance_as_per_books} type={r.books_type} />],
                  ["Amounts not reflected in bank", <Amt key="n" v={r.amounts_not_reflected_in_bank} />],
                  ["Balance as per bank", <span key="k" className="font-semibold text-ink tabular">{inr(r.balance_as_per_bank)}</span>],
                ]} />
                <p className="text-[12px] text-fg-muted">As on {accDate(r.as_of)} · {r.entries.filter((e) => !e.bank_reconciliation_date).length} pending <Badge tone="sky">{r.statement_lines.length} statement lines</Badge></p>
              </Card>
            </div>
            <StatementLines ledgerId={ledgerId} entries={r.entries} />
          </>
        )}
      </QueryState>
    </>
  );
}
