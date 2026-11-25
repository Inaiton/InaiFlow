"use client";

import { CalendarClock } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, DataTable, DatePicker, EmptyState, PageHeader, StatusBadge, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { monthKey, monthLabel, todayIso } from "@/core/dates";
import { Can } from "@/core/permissions/Can";
import { Amt } from "../components/Amount";
import { QueryState } from "../components/QueryState";
import { PAYROLL_NAV, SubNav } from "../components/SubNav";
import { useAccHref } from "../lib/api-base";
import { formatDateTime } from "@/core/dates";
import { useCreatePayrollRun, usePayrollRuns } from "./api";

type Run = Schemas["PayrollRunSummary"];

/** /accounts/payroll — monthly pay runs (design: Acc-Payroll). */
export function PayRunsPage() {
  const href = useAccHref();
  const router = useRouter();
  const runs = usePayrollRuns();
  const create = useCreatePayrollRun();
  const [month, setMonth] = useState(monthKey(todayIso()));
  const cols: ColumnDef<Run, unknown>[] = [
    { accessorKey: "pay_period_month", header: "Month", cell: ({ getValue }) => <span className="font-medium text-fg">{monthLabel((getValue() as string).slice(0, 7))}</span> },
    { accessorKey: "status", header: "Status", cell: ({ getValue }) => <StatusBadge status={getValue() as string} /> },
    { accessorKey: "employee_count", header: "Employees", meta: { align: "right" } },
    { accessorKey: "total_gross", header: "Gross", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "total_net_pay", header: "Net pay", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "locked_at", header: "Locked", cell: ({ getValue }) => (getValue() ? formatDateTime(getValue() as string) : "—") },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Payroll" }]} title="Payroll" description="Compute → lock (posts the payroll voucher, allocates direct labour to runs) → mark paid"
        actions={<Can permission="accounts.payroll_runs" level="WRITE"><div className="w-40"><DatePicker mode="month" aria-label="Pay month" value={month} onValueChange={(v) => v && setMonth(v)} /></div>
          <Button variant="primary" loading={create.isPending} onClick={() => create.mutate(month, { onSuccess: (r) => router.push(href(`/payroll/runs/${r.id}`)) })}>Process {monthLabel(month)}</Button></Can>} />
      <SubNav items={PAYROLL_NAV} />
      <Card padded={false}>
        <QueryState q={runs}>{(list) => <DataTable columns={cols} data={list} getRowId={(r) => r.id} onRowClick={(r) => router.push(href(`/payroll/runs/${r.id}`))} aria-label="Pay runs"
          empty={<EmptyState icon={CalendarClock} title="No pay runs yet" description="Finalize attendance, then process the month." />} />}</QueryState>
      </Card>
    </>
  );
}
