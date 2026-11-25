"use client";

import { Download, FileText } from "lucide-react";
import type { ReactNode } from "react";
import { Button, PageHeader } from "@/components/ui";
import { useAccHref } from "../lib/api-base";
import { periodLabel, type Period } from "../lib/period";
import { accDate } from "../lib/format";
import { PeriodDialog } from "../components/PeriodDialog";
import { useRBar, type RBarItem } from "../shell/rbar-context";
import { useReportExport, type ExportQuery } from "./api";

export function ExportButtons({ report, query }: { report: string; query: Omit<ExportQuery, "format"> }) {
  const exp = useReportExport();
  return (
    <>
      <Button variant="ghost" loading={exp.isPending && exp.variables?.query.format === "csv"} onClick={() => exp.mutate({ report, query: { ...query, format: "csv" } })}><Download />CSV</Button>
      <Button variant="secondary" loading={exp.isPending && exp.variables?.query.format === "pdf"} onClick={() => exp.mutate({ report, query: { ...query, format: "pdf" } })}><FileText />PDF</Button>
    </>
  );
}

/**
 * Report chrome: breadcrumb, title, period (F2), CSV/PDF export (Alt+E / Alt+P via the report button bar).
 * `asOf` reports (balance sheet, ageing) show a single date.
 */
export function ReportFrame({ title, description, report, period, setPeriod, dialogOpen, setDialogOpen, fy, asOf, exportQuery, extraKeys = [], actions, children }: {
  title: string; description?: string; report: string; period: Period; setPeriod: (p: Period) => void; dialogOpen: boolean; setDialogOpen: (o: boolean) => void;
  fy: { start: string; end: string; label: string }; asOf?: boolean; exportQuery: Omit<ExportQuery, "format">; extraKeys?: RBarItem[]; actions?: ReactNode; children: ReactNode;
}) {
  const href = useAccHref();
  const exp = useReportExport();
  useRBar([
    { id: "period", combo: "f2", label: asOf ? "Date" : "Period", run: () => setDialogOpen(true) },
    ...extraKeys,
    { id: "export", combo: "alt+e", label: "Export CSV", sep: true, run: () => exp.mutate({ report, query: { ...exportQuery, format: "csv" } }) },
    { id: "print", combo: "alt+p", label: "Print PDF", run: () => exp.mutate({ report, query: { ...exportQuery, format: "pdf" } }) },
    { id: "exceptions", combo: "ctrl+j", label: "Exceptions", href: href("/utilities") },
    { id: "reports", combo: "alt+r", label: "All reports", href: href("/reports") },
  ], "accounts");
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Reports", href: href("/reports") }, { label: title }]} title={title}
        description={description ?? (asOf ? `As on ${accDate(period.to)}` : periodLabel(period))}
        actions={<>{actions}<ExportButtons report={report} query={exportQuery} /><Button variant="primary" onClick={() => setDialogOpen(true)}>{asOf ? "Change date" : "Change period"} (F2)</Button></>} />
      {children}
      <PeriodDialog open={dialogOpen} onOpenChange={setDialogOpen} period={period} fy={fy} onApply={setPeriod} single={asOf} />
    </>
  );
}
