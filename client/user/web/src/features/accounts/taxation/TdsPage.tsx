"use client";

import { useState } from "react";
import { Badge, Button, Card, DataTable, DatePicker, EmptyState, Field, KeyValue, NativeSelect, PageHeader, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { monthKey, monthLabel, todayIso } from "@/core/dates";
import { Amt } from "../components/Amount";
import { JsonTable } from "../components/JsonTable";
import { QueryState } from "../components/QueryState";
import { SubNav, TAX_NAV } from "../components/SubNav";
import { useAccHref } from "../lib/api-base";
import { accDate, inr } from "../lib/format";
import { fyQuarters } from "../lib/period";
import { usePeriod } from "../lib/use-period";
import { useTdsChallan, useTdsReturn, useTdsSections, useTdsSummary } from "./api";

type Sec = Schemas["TdsSectionOut"];
type Sum = Schemas["TdsSummaryRow"];

/** /accounts/taxation/tds — sections, deductions summary, ITNS 281 challan, 26Q/27Q/27EQ files (design: Acc-Tax-TDS). */
export function TdsPage() {
  const href = useAccHref();
  const { period, fy } = usePeriod();
  const [month, setMonth] = useState(monthKey(todayIso()));
  const quarters = fyQuarters(fy.start);
  const [quarter, setQuarter] = useState(quarters[0]!.key);
  const sections = useTdsSections();
  const summary = useTdsSummary(period.from, period.to);
  const challan = useTdsChallan(month);
  const ret = useTdsReturn();
  const secCols: ColumnDef<Sec, unknown>[] = [
    { accessorKey: "section", header: "Section", cell: ({ getValue }) => <span className="font-semibold">{getValue() as string}</span> },
    { accessorKey: "nature", header: "Nature of payment" },
    { accessorKey: "threshold_single", header: "Single", meta: { align: "right" }, cell: ({ getValue }) => (getValue() ? <Amt v={getValue() as string} /> : "—") },
    { accessorKey: "threshold_annual", header: "Annual", meta: { align: "right" }, cell: ({ getValue }) => (getValue() ? <Amt v={getValue() as string} /> : "—") },
    { accessorKey: "rate_individual", header: "Indiv/HUF %", meta: { align: "right" } },
    { accessorKey: "rate_company", header: "Company %", meta: { align: "right" } },
    { accessorKey: "rate_no_pan", header: "No PAN %", meta: { align: "right" } },
  ];
  const sumCols: ColumnDef<Sum, unknown>[] = [
    { accessorKey: "section", header: "Section" }, { accessorKey: "party_name", header: "Deductee" }, { accessorKey: "pan", header: "PAN", cell: ({ getValue }) => (getValue() as string | null) ?? <Badge tone="danger">No PAN</Badge> },
    { accessorKey: "amount_paid", header: "Paid / credited", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "tds_amount", header: "TDS", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "deposited", header: "Deposited", cell: ({ getValue }) => (getValue() ? <Badge tone="success">Yes</Badge> : <Badge tone="warning">Pending</Badge>) },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Taxation", href: href("/taxation") }, { label: "TDS / TCS" }]} title="TDS / TCS" description={`Deductions ${accDate(period.from)} – ${accDate(period.to)}`} />
      <SubNav items={TAX_NAV} />
      <Card padded={false} title="Deductions by party"><QueryState q={summary}>{(rows) => <DataTable columns={sumCols} data={rows} getRowId={(r) => `${r.section}-${r.party_ledger_id}`} aria-label="TDS summary" empty={<EmptyState title="No TDS deducted in this period" />} />}</QueryState></Card>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card title="Challan (ITNS 281)" actions={<div className="w-40"><DatePicker mode="month" aria-label="Challan month" value={month} onValueChange={(v) => v && setMonth(v)} /></div>}>
          <QueryState q={challan} rows={2}>{(c) => (
            <div className="flex flex-col gap-3">
              <KeyValue rows={[["Month", monthLabel(c.month)], ["Due date", accDate(c.due_date)], ["Total to deposit", <span key="t" className="font-semibold text-ink">{inr(c.total)}</span>]]} />
              <JsonTable rows={c.by_section} label="sections" />
            </div>
          )}</QueryState>
        </Card>
        <Card title="Quarterly return files" description="Text files for the RPU / return preparation utility">
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Quarter"><NativeSelect value={quarter} onChange={(e) => setQuarter(e.target.value)}>{quarters.map((q) => <option key={q.key} value={q.key}>{q.label}</option>)}</NativeSelect></Field>
            {["26Q", "27Q", "27EQ"].map((f) => <Button key={f} variant="secondary" loading={ret.isPending && ret.variables?.form === f} onClick={() => ret.mutate({ form: f, quarter })}>{f}</Button>)}
          </div>
        </Card>
      </div>
      <Card padded={false} title="TDS / TCS sections" description="From the statutory config in force today"><QueryState q={sections}>{(rows) => <DataTable columns={secCols} data={rows} getRowId={(s) => s.section} aria-label="TDS sections" />}</QueryState></Card>
    </>
  );
}
