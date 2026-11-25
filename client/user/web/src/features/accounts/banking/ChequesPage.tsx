"use client";

import { Plus, Printer } from "lucide-react";
import { useState } from "react";
import { Button, Card, DataTable, Dialog, DialogContent, EmptyState, Field, FieldRow, Input, NativeSelect, PageHeader, StatusBadge, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { Can } from "@/core/permissions/Can";
import { Amt } from "../components/Amount";
import { QueryState } from "../components/QueryState";
import { BANKING_NAV, SubNav } from "../components/SubNav";
import { useDialogGuard } from "../components/dialog-guard";
import { useAccHref } from "../lib/api-base";
import { accDate } from "../lib/format";
import { usePeriod } from "../lib/use-period";
import { useBankAccounts, useChequeBooks, useCheques, useCreateChequeBook, usePrintCheque } from "./api";

type Cheque = Schemas["ChequeOut"];

function NewBook({ banks, onClose }: { banks: Schemas["BankAccountOut"][]; onClose: () => void }) {
  useDialogGuard();
  const save = useCreateChequeBook();
  const [f, setF] = useState({ bank_ledger_id: banks[0]?.ledger_id ?? "", from_number: "", to_number: "" });
  const ok = f.bank_ledger_id && /^\d+$/.test(f.from_number) && /^\d+$/.test(f.to_number) && f.from_number.length === f.to_number.length && f.from_number <= f.to_number;
  return (
    <DialogContent title="Add cheque book" size="sm" footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!ok} loading={save.isPending} onClick={async () => { await save.mutateAsync(f); onClose(); }}>Add</Button></>}>
      <div className="flex flex-col gap-3">
        <Field label="Bank"><NativeSelect value={f.bank_ledger_id} onChange={(e) => setF({ ...f, bank_ledger_id: e.target.value })}>{banks.map((b) => <option key={b.ledger_id} value={b.ledger_id}>{b.name}</option>)}</NativeSelect></Field>
        <FieldRow><Field label="From no."><Input inputMode="numeric" value={f.from_number} onChange={(e) => setF({ ...f, from_number: e.target.value })} /></Field><Field label="To no."><Input inputMode="numeric" value={f.to_number} onChange={(e) => setF({ ...f, to_number: e.target.value })} /></Field></FieldRow>
      </div>
    </DialogContent>
  );
}

/** /accounts/banking/cheques — cheque books, cheque register, cheque printing (design: Acc-B-Cheques, Acc-B-ChequePrint). */
export function ChequesPage() {
  const href = useAccHref();
  const { period } = usePeriod();
  const [bank, setBank] = useState("");
  const [adding, setAdding] = useState(false);
  const banks = useBankAccounts();
  const books = useChequeBooks(bank || undefined);
  const cheques = useCheques({ ...(bank ? { bank_ledger_id: bank } : {}), date_from: period.from, date_to: period.to });
  const print = usePrintCheque();
  const cols: ColumnDef<Cheque, unknown>[] = [
    { accessorKey: "instrument_no", header: "Cheque no.", cell: ({ getValue }) => <span className="font-mono">{getValue() as string}</span> },
    { accessorKey: "instrument_date", header: "Cheque date", cell: ({ getValue }) => accDate(getValue() as string | null) },
    { accessorKey: "payee", header: "Payee" },
    { accessorKey: "voucher_number", header: "Voucher" },
    { accessorKey: "amount", header: "Amount", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "status", header: "Status", cell: ({ getValue }) => <StatusBadge status={getValue() as string} /> },
    { id: "p", header: "", cell: ({ row: { original: c } }) => <Button size="sm" variant="ghost" loading={print.isPending && print.variables === c.entry_id} onClick={() => print.mutate(c.entry_id)}><Printer />Print</Button> },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Banking", href: href("/banking") }, { label: "Cheques" }]} title="Cheques" description="Cheque books and register for the selected period"
        actions={<Can permission="accounts.banking" level="WRITE"><Button variant="primary" disabled={!banks.data?.length} onClick={() => setAdding(true)}><Plus />Add cheque book</Button></Can>} />
      <SubNav items={BANKING_NAV} />
      <div className="w-72"><Field label="Bank"><NativeSelect value={bank} onChange={(e) => setBank(e.target.value)}><option value="">All banks</option>{(banks.data ?? []).map((b) => <option key={b.ledger_id} value={b.ledger_id}>{b.name}</option>)}</NativeSelect></Field></div>
      <Card title="Cheque books">
        <QueryState q={books} rows={2}>{(list) => list.length === 0 ? <p className="text-[12.5px] text-fg-muted">No cheque books.</p> : (
          <ul className="grid gap-2 md:grid-cols-3">{list.map((b) => <li key={b.id} className="rounded-lg border border-line p-3 text-[12.5px]"><p className="font-semibold text-ink">{b.bank_name}</p><p className="font-mono">{b.from_number}–{b.to_number}</p><p className="text-fg-muted">Next {b.next_number} · {b.used_count} used</p></li>)}</ul>
        )}</QueryState>
      </Card>
      <Card padded={false} title="Cheque register"><QueryState q={cheques}>{(list) => <DataTable columns={cols} data={list} getRowId={(c) => c.entry_id} aria-label="Cheque register" empty={<EmptyState title="No cheques in this period" />} />}</QueryState></Card>
      <Dialog open={adding} onOpenChange={setAdding}>{adding ? <NewBook banks={banks.data ?? []} onClose={() => setAdding(false)} /> : null}</Dialog>
    </>
  );
}
