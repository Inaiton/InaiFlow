"use client";

import { Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, DataTable, DatePicker, Dialog, DialogContent, EmptyState, ErrorState, Field, Input, KeyValue, NativeSelect, PageHeader, Skeleton, SwitchRow, type ColumnDef } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { todayIso } from "@/core/dates";
import { Can } from "@/core/permissions/Can";
import { Amt } from "../components/Amount";
import { PAYROLL_NAV, SubNav } from "../components/SubNav";
import { useDialogGuard } from "../components/dialog-guard";
import { useAccHref } from "../lib/api-base";
import { accDate, humanize, inr } from "../lib/format";
import { useDebouncedValue } from "../lib/hooks";
import { useEmployee, useEmployees, useExitEmployee, type Employee } from "./api";

/** /accounts/payroll/employees (design: Acc-Pay-Employees). */
export function EmployeesPage() {
  const href = useAccHref();
  const router = useRouter();
  const [text, setText] = useState("");
  const [cat, setCat] = useState("");
  const [exited, setExited] = useState(false);
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(text, 250);
  const list = useEmployees({ limit: 50, offset, ...(q ? { q } : {}), ...(cat ? { category: cat } : {}), ...(exited ? { include_exited: true } : {}) });
  const cols: ColumnDef<Employee, unknown>[] = [
    { accessorKey: "emp_code", header: "Code", cell: ({ getValue }) => <span className="font-mono text-[12px]">{getValue() as string}</span> },
    { accessorKey: "full_name", header: "Name", cell: ({ row: { original: e } }) => <span className="flex flex-col"><span className="font-medium text-fg">{e.full_name}</span><span className="text-[11.5px] text-fg-muted">{[e.designation, e.department].filter(Boolean).join(" · ")}</span></span> },
    { accessorKey: "employee_category", header: "Category", cell: ({ getValue }) => humanize(getValue() as string) },
    { accessorKey: "date_of_joining", header: "Joined", cell: ({ getValue }) => accDate(getValue() as string) },
    { accessorKey: "monthly_gross", header: "Monthly gross", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { id: "s", header: "Status", cell: ({ row: { original: e } }) => (e.is_active ? <Badge tone="success">Active</Badge> : <Badge>Exited {accDate(e.date_of_exit)}</Badge>) },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Payroll", href: href("/payroll") }, { label: "Employees" }]} title="Employees" description="Employee master with UAN, ESIC IP, PAN, bank and salary structure"
        actions={<Can permission="accounts.payroll_employees" level="WRITE"><Button asChild variant="primary"><Link href={href("/payroll/employees/new")}>New employee</Link></Button></Can>} />
      <SubNav items={PAYROLL_NAV} />
      <Card padded={false}>
        <div className="grid grid-cols-1 gap-3 border-b border-line p-4 md:grid-cols-[minmax(0,1fr)_220px_200px] md:items-end">
          <Field label="Search"><Input value={text} onChange={(e) => { setOffset(0); setText(e.target.value); }} placeholder="Name or code" /></Field>
          <Field label="Category"><NativeSelect value={cat} onChange={(e) => { setOffset(0); setCat(e.target.value); }}><option value="">All</option><option value="SHOP_FLOOR_OPERATOR">Shop-floor operator</option><option value="STAFF">Staff</option><option value="MANAGEMENT">Management</option></NativeSelect></Field>
          <SwitchRow label="Include exited" checked={exited} onCheckedChange={(v) => { setOffset(0); setExited(v); }} />
        </div>
        {list.isError ? <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} /> : (
          <DataTable columns={cols} data={list.data?.items} loading={list.isPending} getRowId={(e) => e.id} onRowClick={(e) => router.push(href(`/payroll/employees/${e.id}`))} aria-label="Employees"
            pagination={list.data ? { total: list.data.total, limit: list.data.limit, offset: list.data.offset, onOffsetChange: setOffset } : undefined}
            empty={<EmptyState icon={Users} title="No employees yet" />} />
        )}
      </Card>
    </>
  );
}

function ExitDialog({ emp, onClose }: { emp: Employee; onClose: () => void }) {
  useDialogGuard();
  const exit = useExitEmployee();
  const [date, setDate] = useState(todayIso());
  return (
    <DialogContent title={`Record exit · ${emp.full_name}`} description="The employee is excluded from pay runs after this date. Full & final is processed in the month’s run." size="sm"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="destructive-solid" loading={exit.isPending} onClick={async () => { await exit.mutateAsync({ id: emp.id, date }); onClose(); }}>Record exit</Button></>}>
      <Field label="Date of exit"><DatePicker value={date} onValueChange={(v) => setDate(v ?? todayIso())} /></Field>
    </DialogContent>
  );
}

/** /accounts/payroll/employees/[id] */
export function EmployeeDetail({ id }: { id: string }) {
  const href = useAccHref();
  const q = useEmployee(id);
  const [exitOpen, setExitOpen] = useState(false);
  if (q.isPending) return <Skeleton className="h-96 w-full" />;
  if (q.isError) return <ErrorState message={describeError(q.error)} onRetry={() => void q.refetch()} />;
  const e = q.data;
  const s = e.salary_structure;
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Employees", href: href("/payroll/employees") }, { label: e.full_name }]} title={e.full_name}
        description={`${e.emp_code} · ${humanize(e.employee_category)} · ${inr(e.monthly_gross)} / month`}
        actions={<>
          {e.is_active ? <Can permission="accounts.payroll_employees" level="FULL"><Button variant="destructive" onClick={() => setExitOpen(true)}>Record exit</Button></Can> : null}
          <Can permission="accounts.payroll_employees" level="WRITE"><Button asChild variant="primary"><Link href={href(`/payroll/employees/${id}/edit`)}>Alter employee</Link></Button></Can>
        </>} />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card title="Employee"><KeyValue rows={[["Department", e.department ?? "—"], ["Designation", e.designation ?? "—"], ["Joined", accDate(e.date_of_joining)], ["Exit", accDate(e.date_of_exit)],
          ["PAN", e.pan ?? "—"], ["UAN", e.uan_epf ?? "—"], ["ESIC IP", e.esic_ip_no ?? "—"], ["Bank", e.bank_account_no ? `${e.bank_account_no} · ${e.bank_ifsc ?? ""}` : "—"], ["Tax regime", humanize(e.tax_regime)]]} /></Card>
        <Card title="Salary structure"><KeyValue rows={[["Basic", inr(s.basic)], ["DA", inr(s.da)], ["HRA", inr(s.hra)], ["Special", inr(s.special)], ["Conveyance", inr(s.conveyance)],
          ...(s.other_allowances ?? []).map((a) => [a.name, inr(a.amount)] as [string, string]), ...(s.other_deductions ?? []).map((d) => [`Less: ${d.name}`, inr(d.amount)] as [string, string]),
          ["Piece rate", s.piece_rate ? inr(s.piece_rate) : "—"], ["Statutory", [s.epf_applicable && "EPF", s.esic_applicable && "ESIC", s.pt_applicable && "PT"].filter(Boolean).join(" · ") || "None"]]} /></Card>
      </div>
      <Dialog open={exitOpen} onOpenChange={setExitOpen}>{exitOpen ? <ExitDialog emp={e} onClose={() => setExitOpen(false)} /> : null}</Dialog>
    </>
  );
}
