"use client";

import { Download, FileText } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, ConfirmDialog, DatePicker, Dialog, DialogContent, Field, KpiCard, KpiGrid, PageHeader, StatusBadge } from "@/components/ui";
import { Banknote, Building, Users, Wallet } from "lucide-react";
import type { Schemas } from "@/core/api/types";
import { monthLabel, todayIso } from "@/core/dates";
import { Can } from "@/core/permissions/Can";
import { Amt } from "../components/Amount";
import { LedgerPicker } from "../components/LedgerPicker";
import { QueryState } from "../components/QueryState";
import { useDialogGuard } from "../components/dialog-guard";
import { useAccHref } from "../lib/api-base";
import { humanize, inr, qty } from "../lib/format";
import { usePayrollFile, usePayrollRun, usePayrollRunAction } from "./api";

type Line = Schemas["PayrollLineOut"];

const Breakdown = ({ m }: { m: Record<string, string> }) => (
  <ul className="text-[11.5px] text-fg-3">{Object.entries(m).map(([k, v]) => <li key={k} className="flex justify-between gap-3"><span>{humanize(k)}</span><Amt v={v} /></li>)}</ul>
);

function PaidDialog({ onSubmit, onClose, loading }: { onSubmit: (b: Schemas["MarkPaidIn"]) => void; onClose: () => void; loading: boolean }) {
  useDialogGuard();
  const [bank, setBank] = useState<string | null>(null);
  const [date, setDate] = useState(todayIso());
  return (
    <DialogContent title="Mark salaries paid" description="Posts a payment voucher: Dr Salary Payable, Cr bank" size="sm"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!bank} loading={loading} onClick={() => bank && onSubmit({ bank_ledger_id: bank, payment_date: date })}>Mark paid</Button></>}>
      <div className="flex flex-col gap-3">
        <Field label="Bank ledger"><div className="rounded-lg border border-line"><LedgerPicker value={bank} filter={{ bank_only: true }} onChange={(l) => setBank(l.id)} /></div></Field>
        <Field label="Payment date"><DatePicker value={date} onValueChange={(v) => setDate(v ?? todayIso())} /></Field>
      </div>
    </DialogContent>
  );
}

/** /accounts/payroll/runs/[id] — lines, recompute, lock (FULL), mark paid, bank file, payslips, statutory files (design: Acc-Pay-Lock, Acc-Pay-Statutory). */
export function PayRunDetail({ id }: { id: string }) {
  const href = useAccHref();
  const router = useRouter();
  const q = usePayrollRun(id);
  const act = usePayrollRunAction(id);
  const file = usePayrollFile();
  const [lockKey] = useState(() => crypto.randomUUID());
  const [confirm, setConfirm] = useState<"lock" | "delete" | null>(null);
  const [paid, setPaid] = useState(false);
  return (
    <QueryState q={q} rows={8}>
      {(r) => {
        const draft = r.status === "DRAFT";
        return (
          <>
            <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Payroll", href: href("/payroll") }, { label: monthLabel(r.pay_period_month.slice(0, 7)) }]}
              title={<span className="flex items-center gap-2">Pay run · {monthLabel(r.pay_period_month.slice(0, 7))} <StatusBadge status={r.status} /></span>}
              description={r.locked_at ? `Locked by ${r.locked_by_name ?? "—"}` : "Draft — recompute after attendance changes, then lock"}
              actions={<>
                {draft ? <Can permission="accounts.payroll_runs" level="WRITE"><Button variant="secondary" loading={act.isPending && act.variables?.kind === "recompute"} onClick={() => act.mutate({ kind: "recompute" })}>Recompute</Button></Can> : null}
                {draft ? <Can permission="accounts.payroll_runs" level="FULL"><Button variant="destructive" onClick={() => setConfirm("delete")}>Delete</Button><Button variant="primary" onClick={() => setConfirm("lock")}>Lock & post</Button></Can> : null}
                {r.status === "LOCKED_POSTED" ? <Can permission="accounts.payroll_runs" level="FULL"><Button variant="primary" onClick={() => setPaid(true)}>Mark paid</Button></Can> : null}
              </>} />
            <KpiGrid>
              <KpiCard title="Employees" icon={Users} tone="indigo" value={String(r.employee_count)} />
              <KpiCard title="Gross" icon={Wallet} tone="teal" value={inr(r.total_gross, 0)} />
              <KpiCard title="Deductions" icon={Building} tone="orange" value={inr(r.total_deductions, 0)} caption={`Employer contrib ${inr(r.total_employer_contrib, 0)}`} />
              <KpiCard title="Net pay" icon={Banknote} tone="accent" value={inr(r.total_net_pay, 0)} />
            </KpiGrid>
            {!draft ? (
              <Card title="Files & postings">
                <div className="flex flex-wrap gap-2">
                  {r.posted_voucher_id ? <Button asChild variant="secondary"><Link href={href(`/vouchers/${r.posted_voucher_id}`)}>Payroll voucher</Link></Button> : null}
                  {r.payment_voucher_id ? <Button asChild variant="secondary"><Link href={href(`/vouchers/${r.payment_voucher_id}`)}>Payment voucher</Link></Button> : null}
                  <Can permission="accounts.payroll_runs" level="FULL"><Button variant="secondary" onClick={() => file.mutate({ kind: "bank", runId: id })}><Download />Bank file (NEFT)</Button></Can>
                  {[["epf-ecr", "EPF ECR"], ["esic", "ESIC"], ["pt", "Professional tax"]].map(([k, l]) => <Button key={k} variant="ghost" onClick={() => file.mutate({ kind: "statutory", runId: id, statutory: k! })}><Download />{l}</Button>)}
                </div>
              </Card>
            ) : null}
            <Card padded={false} title="Employees">
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead><tr className="border-b border-line bg-subtle text-[11.5px] text-fg-muted">{["Employee", "Days / LOP / OT", "Earnings", "Deductions", "Employer", "Gross", "Net pay", ""].map((h) => <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>)}</tr></thead>
                  <tbody>{r.lines.map((l: Line) => (
                    <tr key={l.id} className="border-b border-line/60 align-top">
                      <td className="px-3 py-2"><span className="font-medium text-fg">{l.full_name}</span><span className="block text-[11.5px] text-fg-muted">{l.emp_code} · {humanize(l.employee_category)}</span></td>
                      <td className="px-3 py-2 tabular">{qty(l.days_worked)} / {qty(l.lop_days)} / {qty(l.overtime_hours)}</td>
                      <td className="min-w-40 px-3 py-2"><Breakdown m={l.earnings_breakdown} /></td>
                      <td className="min-w-40 px-3 py-2"><Breakdown m={l.deductions_breakdown} /></td>
                      <td className="min-w-36 px-3 py-2"><Breakdown m={l.employer_contrib_breakdown} /></td>
                      <td className="px-3 py-2 text-right"><Amt v={l.gross} /></td>
                      <td className="px-3 py-2 text-right"><Amt v={l.net_pay} strong /></td>
                      <td className="px-3 py-2">{!draft ? <Button size="sm" variant="ghost" onClick={() => file.mutate({ kind: "payslip", runId: id, lineId: l.id })}><FileText />Payslip</Button> : null}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </Card>
            <ConfirmDialog open={confirm === "lock"} onOpenChange={(o) => !o && setConfirm(null)} title={`Lock payroll for ${monthLabel(r.pay_period_month.slice(0, 7))}?`}
              description="Posts the payroll voucher (Dr wages per cost centre, Cr salary & statutory payables), allocates shop-floor wages to period runs and files payslips. This can’t be undone."
              confirmText="LOCK" confirmLabel="Lock & post" loading={act.isPending} onConfirm={async () => { await act.mutateAsync({ kind: "lock", key: lockKey }); setConfirm(null); }} />
            <ConfirmDialog open={confirm === "delete"} onOpenChange={(o) => !o && setConfirm(null)} title="Delete this draft run?" destructive confirmLabel="Delete" loading={act.isPending}
              onConfirm={async () => { await act.mutateAsync({ kind: "delete" }); router.push(href("/payroll")); }} />
            <Dialog open={paid} onOpenChange={setPaid}>{paid ? <PaidDialog loading={act.isPending} onClose={() => setPaid(false)} onSubmit={async (b) => { await act.mutateAsync({ kind: "paid", body: b }); setPaid(false); }} /> : null}</Dialog>
          </>
        );
      }}
    </QueryState>
  );
}
