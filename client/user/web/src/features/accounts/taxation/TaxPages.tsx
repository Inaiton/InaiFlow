"use client";

import { Download } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { Badge, Button, Card, DataTable, DatePicker, EmptyState, KpiCard, KpiGrid, PageHeader, Tabs, TabsContent, TabsList, TabsTrigger, type ColumnDef } from "@/components/ui";
import { Receipt, ShieldAlert, ArrowDownLeft, ArrowUpRight } from "lucide-react";
import type { Schemas } from "@/core/api/types";
import { monthKey, monthLabel, todayIso } from "@/core/dates";
import { add } from "@/core/money";
import { Amt } from "../components/Amount";
import { JsonSection, JsonTable } from "../components/JsonTable";
import { QueryState } from "../components/QueryState";
import { SubNav, TAX_NAV } from "../components/SubNav";
import { useAccHref } from "../lib/api-base";
import { inr } from "../lib/format";
import { useGstExport, useGstr1, useGstr3b, useGstSummary, useGstValidate } from "./api";

type Issue = Schemas["GstValidationIssue"];
type Totals = Schemas["GstTotals"];

/** Shared header for GST screens: month picker + section tabs. */
export function TaxShell({ title, description, period, setPeriod, actions, children }: { title: string; description: string; period: string; setPeriod: (p: string) => void; actions?: ReactNode; children: ReactNode }) {
  const href = useAccHref();
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Taxation", href: href("/taxation") }, { label: title }]} title={title} description={`${description} · ${monthLabel(period)}`}
        actions={<><div className="w-44"><DatePicker mode="month" aria-label="Return period" value={period} onValueChange={(v) => v && setPeriod(v)} /></div>{actions}</>} />
      <SubNav items={TAX_NAV} />
      {children}
    </>
  );
}

export const useMonth = () => useState(monthKey(todayIso()));

function TotalsRow({ label, t }: { label: string; t: Totals }) {
  return <tr className="border-b border-line/60"><td className="px-3 py-1.5 font-medium text-fg">{label}</td>{(["taxable", "igst", "cgst", "sgst", "cess"] as const).map((k) => <td key={k} className="px-3 text-right"><Amt v={t[k]} /></td>)}</tr>;
}

/** /accounts/taxation — GST summary for the month (design: Acc-GST). */
export function GstSummaryPage() {
  const [period, setPeriod] = useMonth();
  const href = useAccHref();
  const q = useGstSummary(period);
  return (
    <TaxShell title="GST summary" description="Outward liability, ITC and net payable" period={period} setPeriod={setPeriod}>
      <QueryState q={q}>
        {(s) => (
          <>
            <KpiGrid>
              <KpiCard title="Outward tax" icon={ArrowUpRight} tone="orange" value={inr(sumTax(s.outward), 0)} caption={`Taxable ${inr(s.outward.taxable, 0)}`} />
              <KpiCard title="Input tax credit" icon={ArrowDownLeft} tone="teal" value={inr(sumTax(s.inward_itc), 0)} />
              <KpiCard title="RCM liability" icon={ShieldAlert} tone="warning" value={inr(sumTax(s.rcm_liability), 0)} />
              <KpiCard title="Net payable" icon={Receipt} tone="accent" value={inr(sumTax(s.net_payable), 0)} caption={`${s.voucher_count} vouchers`} />
            </KpiGrid>
            <Card padded={false} title="Tax position">
              <table className="w-full text-[13px]"><thead><tr className="border-b border-line bg-subtle text-[11.5px] text-fg-muted">{["", "Taxable", "IGST", "CGST", "SGST", "Cess"].map((h) => <th key={h} className={`px-3 py-2 font-semibold ${h ? "text-right" : "text-left"}`}>{h}</th>)}</tr></thead>
                <tbody><TotalsRow label="Outward supplies" t={s.outward} /><TotalsRow label="Input tax credit" t={s.inward_itc} /><TotalsRow label="RCM liability" t={s.rcm_liability} /><TotalsRow label="Net payable" t={s.net_payable} /></tbody></table>
            </Card>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="secondary"><Link href={href("/taxation/gstr1")}>GSTR-1</Link></Button><Button asChild variant="secondary"><Link href={href("/taxation/gstr3b")}>GSTR-3B</Link></Button>
              <Button asChild variant="secondary"><Link href={href("/taxation/gstr2b")}>GSTR-2B reconciliation</Link></Button><Button asChild variant="secondary"><Link href={href("/taxation/validate")}>Pre-filing validator</Link></Button>
            </div>
          </>
        )}
      </QueryState>
    </TaxShell>
  );
}

const sumTax = (t: Totals) => add(t.igst, t.cgst, t.sgst, t.cess);

export function IssuesTable({ issues }: { issues: Issue[] }) {
  const href = useAccHref();
  const cols: ColumnDef<Issue, unknown>[] = [
    { accessorKey: "severity", header: "Severity", cell: ({ getValue }) => <Badge tone={getValue() === "ERROR" ? "danger" : "warning"}>{getValue() as string}</Badge> },
    { accessorKey: "code", header: "Rule", cell: ({ getValue }) => <span className="font-mono text-[12px]">{getValue() as string}</span> },
    { accessorKey: "message", header: "Message" },
    { id: "v", header: "Voucher", cell: ({ row: { original: i } }) => (i.voucher_id ? <Link href={href(`/vouchers/${i.voucher_id}`)}>{i.voucher_number ?? "Open"}</Link> : "—") },
  ];
  return <DataTable columns={cols} data={issues} getRowId={(i) => `${i.code}-${i.voucher_id ?? ""}-${i.message}`} aria-label="Validation issues" empty={<EmptyState tone="success" title="No issues — ready to file" />} />;
}

function ExportButton({ form, period }: { form: "gstr1" | "gstr3b"; period: string }) {
  const exp = useGstExport();
  return <Button variant="primary" loading={exp.isPending} onClick={() => exp.mutate({ form, period })}><Download />Export JSON</Button>;
}

const GSTR1_TABS = ["b2b", "b2cl", "b2cs", "cdnr", "cdnur", "exp", "hsn"] as const;

/** /accounts/taxation/gstr1 (design: Acc-Tax-GSTR1). */
export function Gstr1Page() {
  const [period, setPeriod] = useMonth();
  const q = useGstr1(period);
  return (
    <TaxShell title="GSTR-1" description="Outward supplies return" period={period} setPeriod={setPeriod} actions={<ExportButton form="gstr1" period={period} />}>
      <QueryState q={q}>
        {(r) => (
          <Card padded={false}>
            <p className="px-5 text-[12.5px] text-fg-muted">GSTIN {r.gstin ?? "not set"} · Taxable {inr(r.totals.taxable)} · IGST {inr(r.totals.igst)} · CGST {inr(r.totals.cgst)} · SGST {inr(r.totals.sgst)}</p>
            <Tabs defaultValue="b2b" className="px-2 pb-2">
              <TabsList>
                {GSTR1_TABS.map((t) => <TabsTrigger key={t} value={t}>{t.toUpperCase()} <span className="text-fg-muted">({r[t].length})</span></TabsTrigger>)}
                <TabsTrigger value="errors">Errors <span className={r.errors.length ? "text-danger-text" : "text-fg-muted"}>({r.errors.length})</span></TabsTrigger>
              </TabsList>
              {GSTR1_TABS.map((t) => <TabsContent key={t} value={t}><JsonTable rows={r[t]} label={t.toUpperCase()} /></TabsContent>)}
              <TabsContent value="errors"><IssuesTable issues={r.errors} /></TabsContent>
            </Tabs>
          </Card>
        )}
      </QueryState>
    </TaxShell>
  );
}

const SECTIONS_3B = [["sec_3_1", "3.1 Outward & RCM supplies"], ["sec_3_2", "3.2 Inter-state to unregistered"], ["sec_4", "4 Eligible ITC"], ["sec_5", "5 Exempt / nil / non-GST inward"], ["sec_6_1", "6.1 Payment of tax"]] as const;

/** /accounts/taxation/gstr3b (design: Acc-Tax-GSTR3B). */
export function Gstr3bPage() {
  const [period, setPeriod] = useMonth();
  const q = useGstr3b(period);
  return (
    <TaxShell title="GSTR-3B" description="Monthly summary return" period={period} setPeriod={setPeriod} actions={<ExportButton form="gstr3b" period={period} />}>
      <QueryState q={q}>{(r) => <div className="flex flex-col gap-4">{SECTIONS_3B.map(([k, label]) => <Card key={k} padded={false} title={label}><div className="pb-3"><JsonSection value={r[k]} label={label} /></div></Card>)}</div>}</QueryState>
    </TaxShell>
  );
}

/** /accounts/taxation/validate (design: Acc-Tax-Validator). */
export function GstValidatePage() {
  const [period, setPeriod] = useMonth();
  const q = useGstValidate(period);
  return (
    <TaxShell title="Pre-filing validator" description="GSTIN, HSN, place of supply and rate checks" period={period} setPeriod={setPeriod}>
      <Card padded={false}><QueryState q={q}>{(issues) => <IssuesTable issues={issues} />}</QueryState></Card>
    </TaxShell>
  );
}

