"use client";

import { useState } from "react";
import { Button, Card, ErrorState, PageHeader } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { sum } from "@/core/money";
import { Amt } from "../components/Amount";
import { PeriodDialog } from "../components/PeriodDialog";
import { VoucherTable } from "../gateway/RecentVouchers";
import { useAccHref } from "../lib/api-base";
import { periodLabel } from "../lib/period";
import { usePeriod } from "../lib/use-period";
import { ExportButtons } from "../reports/ReportFrame";
import { useRBar } from "../shell/rbar-context";
import { voucherKeys } from "../shell/default-rbar";
import { useDayBook } from "./api";

/** /accounts/daybook — all REGULAR vouchers of the period in date order (design: Acc-Daybook). */
export function DayBook() {
  const href = useAccHref();
  const p = usePeriod();
  const [offset, setOffset] = useState(0);
  const q = useDayBook({ date_from: p.period.from, date_to: p.period.to, limit: 100, offset });
  useRBar([{ id: "period", combo: "f2", label: "Period", run: () => p.setDialogOpen(true) }, ...voucherKeys(href).map((i, n) => ({ ...i, sep: n === 0 }))], "accounts");
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Day book" }]} title="Day book" description={periodLabel(p.period)}
        actions={<><ExportButtons report="day-book" query={{ date_from: p.period.from, date_to: p.period.to }} /><Button variant="primary" onClick={() => p.setDialogOpen(true)}>Change period (F2)</Button></>} />
      <Card padded={false}>
        {q.isError ? <ErrorState message={describeError(q.error)} onRetry={() => void q.refetch()} /> : (
          <VoucherTable data={q.data?.items} loading={q.isPending} pagination={q.data ? { total: q.data.total, limit: q.data.limit, offset: q.data.offset, onOffsetChange: setOffset } : undefined} />
        )}
        {q.data ? <div className="flex justify-end gap-6 border-t border-line px-4 py-2.5 text-[13px]"><span className="text-fg-muted">{q.data.total} vouchers</span><span>Page total <Amt strong v={sum(q.data.items.map((v) => v.total_amount))} /></span></div> : null}
      </Card>
      <PeriodDialog open={p.dialogOpen} onOpenChange={p.setDialogOpen} period={p.period} fy={p.fy} onApply={(np) => { setOffset(0); p.setPeriod(np); }} />
    </>
  );
}
