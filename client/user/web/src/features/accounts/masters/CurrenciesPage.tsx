"use client";

import { Coins, Plus } from "lucide-react";
import { useState } from "react";
import { Button, Card, DataTable, DatePicker, DecimalInput, Dialog, DialogContent, EmptyState, Field, FieldRow, Input, PageHeader, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { todayIso } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { Can } from "@/core/permissions/Can";
import { QueryState } from "../components/QueryState";
import { MASTERS_NAV, SubNav } from "../components/SubNav";
import { useDialogGuard } from "../components/dialog-guard";
import { useAccHref } from "../lib/api-base";
import { accDate } from "../lib/format";
import { useAddRate, useCreateCurrency, useCurrencies } from "./api";

type Cur = Schemas["CurrencyOut"];

function NewCurrency({ onClose }: { onClose: () => void }) {
  useDialogGuard();
  const save = useCreateCurrency();
  const [f, setF] = useState({ code: "", symbol: "", name: "", decimal_places: "2" });
  return (
    <DialogContent title="Add currency" size="sm" footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button>
      <Button variant="primary" disabled={!/^[A-Z]{3}$/.test(f.code) || !f.symbol || !f.name} loading={save.isPending} onClick={async () => { await save.mutateAsync({ ...f, decimal_places: Number(f.decimal_places) || 2 }); onClose(); }}>Add</Button></>}>
      <div className="flex flex-col gap-3">
        <FieldRow><Field label="ISO code" required><Input autoFocus value={f.code} maxLength={3} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase() })} placeholder="USD" /></Field><Field label="Symbol" required><Input value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value })} placeholder="$" /></Field></FieldRow>
        <FieldRow><Field label="Name" required><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="US Dollar" /></Field><Field label="Decimals"><Input inputMode="numeric" value={f.decimal_places} onChange={(e) => setF({ ...f, decimal_places: e.target.value })} /></Field></FieldRow>
      </div>
    </DialogContent>
  );
}

function RateDialog({ cur, onClose }: { cur: Cur; onClose: () => void }) {
  useDialogGuard();
  const { context } = useOrg();
  const save = useAddRate();
  const [date, setDate] = useState(todayIso());
  const [rate, setRate] = useState(cur.latest_rate ?? "");
  return (
    <DialogContent title={`Exchange rate · ${cur.code}`} description={`1 ${cur.code} = ? ${context.base_currency_code}`} size="sm"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!rate} loading={save.isPending} onClick={async () => { await save.mutateAsync({ id: cur.id, body: { rate_date: date, rate_to_base: rate } }); onClose(); }}>Save rate</Button></>}>
      <FieldRow><Field label="Date"><DatePicker value={date} onValueChange={(v) => setDate(v ?? todayIso())} /></Field><Field label="Rate"><DecimalInput decimals={4} value={rate} onValueChange={(v) => setRate(v ?? "")} prefix={context.base_currency_symbol} /></Field></FieldRow>
    </DialogContent>
  );
}

/** /accounts/masters/currencies — currencies and dated exchange rates (Forex gain/loss posts to the system ledger). */
export function CurrenciesPage() {
  const href = useAccHref();
  const q = useCurrencies();
  const [adding, setAdding] = useState(false);
  const [rateFor, setRateFor] = useState<Cur | null>(null);
  const cols: ColumnDef<Cur, unknown>[] = [
    { accessorKey: "code", header: "Code", cell: ({ getValue }) => <span className="font-semibold">{getValue() as string}</span> },
    { accessorKey: "symbol", header: "Symbol" }, { accessorKey: "name", header: "Name" },
    { accessorKey: "latest_rate", header: "Latest rate", meta: { align: "right" }, cell: ({ getValue }) => <span className="tabular">{(getValue() as string | null) ?? "—"}</span> },
    { accessorKey: "latest_rate_date", header: "As on", cell: ({ getValue }) => accDate(getValue() as string | null) },
    { id: "act", header: "", cell: ({ row: { original: c } }) => <Can permission="accounts.ledgers_groups" level="WRITE"><Button size="sm" variant="ghost" onClick={() => setRateFor(c)}>Set rate</Button></Can> },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Masters", href: href("/masters") }, { label: "Currencies" }]} title="Currencies" description="Foreign currencies and exchange rates"
        actions={<Can permission="accounts.ledgers_groups" level="WRITE"><Button variant="primary" onClick={() => setAdding(true)}><Plus />Add currency</Button></Can>} />
      <SubNav items={MASTERS_NAV} />
      <Card padded={false}><QueryState q={q}>{(list) => <DataTable columns={cols} data={list} getRowId={(c) => c.id} aria-label="Currencies" empty={<EmptyState icon={Coins} title="Only the base currency" />} />}</QueryState></Card>
      <Dialog open={adding} onOpenChange={setAdding}>{adding ? <NewCurrency onClose={() => setAdding(false)} /> : null}</Dialog>
      <Dialog open={Boolean(rateFor)} onOpenChange={(o) => !o && setRateFor(null)}>{rateFor ? <RateDialog cur={rateFor} onClose={() => setRateFor(null)} /> : null}</Dialog>
    </>
  );
}
