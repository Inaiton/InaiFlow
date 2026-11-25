"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, ConfirmDialog, DataTable, EmptyState, ErrorState, KeyValue, PageHeader, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger, type ColumnDef } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import type { Schemas } from "@/core/api/types";
import { Can, useCan } from "@/core/permissions/Can";
import { Amt, Bal } from "../components/Amount";
import { PeriodDialog } from "../components/PeriodDialog";
import { QueryState } from "../components/QueryState";
import { useAccHref } from "../lib/api-base";
import { accDate, drcr, humanize } from "../lib/format";
import { periodLabel } from "../lib/period";
import { usePeriod } from "../lib/use-period";
import { useRBar } from "../shell/rbar-context";
import { useDeleteLedger, useLedger, useLedgerStatement, useOutstandingBills } from "./api";

type Line = Schemas["LedgerStatementLine"];
type Bill = Schemas["OutstandingBillOut"];

function Statement({ id }: { id: string }) {
  const href = useAccHref();
  const router = useRouter();
  const p = usePeriod();
  const st = useLedgerStatement(id, p.period.from, p.period.to);
  const cols: ColumnDef<Line, unknown>[] = [
    { accessorKey: "date", header: "Date", cell: ({ getValue }) => <span className="tabular whitespace-nowrap">{accDate(getValue() as string)}</span> },
    { accessorKey: "particulars", header: "Particulars", cell: ({ row: { original: l } }) => <span className="flex flex-col"><span className="font-medium text-fg">{l.particulars}</span>{l.narration ? <span className="text-[11.5px] text-fg-muted">{l.narration}</span> : null}</span> },
    { accessorKey: "voucher_type", header: "Vch type" },
    { accessorKey: "voucher_number", header: "Vch no." },
    { accessorKey: "debit", header: "Debit", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} blankZero /> },
    { accessorKey: "credit", header: "Credit", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} blankZero /> },
    { id: "bal", header: "Balance", meta: { align: "right" }, cell: ({ row: { original: l } }) => <Bal v={l.running_balance} type={l.running_type} /> },
  ];
  useRBar([{ id: "period", combo: "f2", label: "Period", run: () => p.setDialogOpen(true) }, { id: "alter", combo: "ctrl+e", label: "Alter ledger", href: href(`/masters/ledgers/${id}/edit`) }], "accounts");
  return (
    <Card padded={false} title={`Ledger statement · ${periodLabel(p.period)}`} actions={<Button size="sm" variant="secondary" onClick={() => p.setDialogOpen(true)}>Period (F2)</Button>}>
      <QueryState q={st}>
        {(s) => (
          <>
            <div className="flex justify-between border-b border-line px-4 py-2 text-[13px]"><span className="text-fg-muted">Opening balance</span><Bal v={s.opening_balance} type={s.opening_type} /></div>
            <DataTable columns={cols} data={s.lines} onRowClick={(l) => router.push(href(`/vouchers/${l.voucher_id}`))} getRowId={(l) => `${l.voucher_id}-${l.running_balance}`} aria-label="Ledger statement"
              empty={<EmptyState title="No transactions in this period" />} />
            <div className="grid grid-cols-[1fr_140px_140px_160px] gap-2 border-t-2 border-fg px-4 py-2 text-[13px] font-semibold">
              <span className="text-right text-fg-muted">Current total</span><Amt v={s.total_debit} className="text-right" /><Amt v={s.total_credit} className="text-right" /><Bal v={s.closing_balance} type={s.closing_type} className="text-right" />
            </div>
          </>
        )}
      </QueryState>
      <PeriodDialog open={p.dialogOpen} onOpenChange={p.setDialogOpen} period={p.period} fy={p.fy} onApply={p.setPeriod} />
    </Card>
  );
}

function Bills({ id }: { id: string }) {
  const bills = useOutstandingBills(id);
  const cols: ColumnDef<Bill, unknown>[] = [
    { accessorKey: "ref_name", header: "Bill ref" },
    { accessorKey: "bill_date", header: "Date", cell: ({ getValue }) => accDate(getValue() as string) },
    { accessorKey: "due_date", header: "Due", cell: ({ getValue }) => accDate(getValue() as string | null) },
    { accessorKey: "amount", header: "Bill amount", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { id: "pending", header: "Pending", meta: { align: "right" }, cell: ({ row: { original: b } }) => <Bal v={b.pending} type={b.pending_type} /> },
    { accessorKey: "overdue_days", header: "Overdue", meta: { align: "right" }, cell: ({ getValue }) => { const d = getValue() as number; return d > 0 ? <Badge tone={d > 45 ? "danger" : "warning"}>{d} days</Badge> : <Badge tone="success">Not due</Badge>; } },
  ];
  return <Card padded={false} title="Outstanding bills"><QueryState q={bills}>{(b) => <DataTable columns={cols} data={b} getRowId={(x) => x.ref_name} aria-label="Outstanding bills" empty={<EmptyState title="No pending bills" />} />}</QueryState></Card>;
}

/** /accounts/masters/ledgers/[id] — profile, statement (drill to voucher), outstanding bills. */
export function LedgerDetail({ id }: { id: string }) {
  const href = useAccHref();
  const router = useRouter();
  const q = useLedger(id);
  const del = useDeleteLedger();
  const canReports = useCan("accounts.reports", "READ");
  const [remove, setRemove] = useState(false);
  if (q.isPending) return <Skeleton className="h-96 w-full" />;
  if (q.isError) return <ErrorState message={describeError(q.error)} onRetry={() => void q.refetch()} />;
  const l = q.data;
  const pd = l.party_details;
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Ledgers", href: href("/masters/ledgers") }, { label: l.name }]}
        title={<span className="flex items-center gap-2">{l.name}{!l.is_active ? <Badge>Inactive</Badge> : null}</span>}
        description={`${l.group_name} · closing ${drcr(l.closing_balance, l.closing_balance_type, { symbol: true })}`}
        actions={<>
          {!l.system_code ? <Can permission="accounts.ledgers_groups" level="FULL"><Button variant="destructive" onClick={() => setRemove(true)}>Delete</Button></Can> : null}
          <Can permission="accounts.ledgers_groups" level="WRITE"><Button asChild variant="primary"><Link href={href(`/masters/ledgers/${id}/edit`)}>Alter ledger</Link></Button></Can>
        </>} />
      <Tabs defaultValue={canReports ? "statement" : "profile"}>
        <TabsList>
          {canReports ? <TabsTrigger value="statement">Statement</TabsTrigger> : null}
          {l.maintain_bill_by_bill ? <TabsTrigger value="bills">Outstanding bills</TabsTrigger> : null}
          <TabsTrigger value="profile">Profile</TabsTrigger>
        </TabsList>
        {canReports ? <TabsContent value="statement"><Statement id={id} /></TabsContent> : null}
        {l.maintain_bill_by_bill ? <TabsContent value="bills"><Bills id={id} /></TabsContent> : null}
        <TabsContent value="profile">
          <Card>
            <KeyValue rows={[
              ["Under group", `${l.group_name} (${humanize(l.nature)})`], ["Opening balance", drcr(l.opening_balance, l.opening_balance_type, { symbol: true })],
              ["Bill-by-bill", l.maintain_bill_by_bill ? "Yes" : "No"], ["Credit period", l.default_credit_days ? `${l.default_credit_days} days` : "—"],
              ["Credit limit", l.credit_limit ? drcr(l.credit_limit, null, { symbol: true }) : "—"], ["GSTIN", pd?.gstin ?? "—"], ["State", pd?.state_code ?? "—"],
              ["PAN", pd?.pan ?? "—"], ["MSME", pd?.msme_type ? `${humanize(pd.msme_type)}${pd.udyam_no ? ` · ${pd.udyam_no}` : ""}` : "Not registered"],
              ["Bank", pd?.bank_account ? `${pd.bank_account} · ${pd.ifsc ?? ""}` : "—"],
              ["Tax config", l.tax_config ? `${l.tax_config.tax_type}${l.tax_config.gst_head ? ` · ${l.tax_config.gst_head}` : ""}${l.tax_config.rate ? ` · ${l.tax_config.rate}%` : ""}${l.tax_config.tds_section ? ` · ${l.tax_config.tds_section}` : ""}` : "—"],
              ["Interest", l.interest_config ? `${l.interest_config.rate_pct}% p.a. · ${humanize(l.interest_config.basis)}` : "—"],
            ]} />
          </Card>
        </TabsContent>
      </Tabs>
      <ConfirmDialog open={remove} onOpenChange={setRemove} title={`Delete ${l.name}?`} description="Ledgers with vouchers can’t be deleted (mark them inactive instead)." destructive confirmLabel="Delete ledger"
        loading={del.isPending} onConfirm={async () => { await del.mutateAsync(id); router.push(href("/masters/ledgers")); }} />
    </>
  );
}
