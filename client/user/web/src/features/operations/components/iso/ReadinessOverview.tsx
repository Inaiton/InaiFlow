"use client";

import { AlertTriangle, Gauge, ShieldCheck } from "lucide-react";
import { ErrorState, KpiCard, KpiGrid, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { formatQty } from "@/core/money";
import { useReadiness } from "../../api/iso";
import { Progress } from "../shared/Progress";

export function ReadinessOverview({ onGo }: { onGo: (tab: string) => void }) {
  const r = useReadiness();
  if (r.isError) return <ErrorState message={describeError(r.error)} onRetry={() => void r.refetch()} />;
  if (!r.data) return <Skeleton className="h-60" />;
  const d = r.data;
  return (
    <div className="flex flex-col gap-5 pt-2">
      <KpiGrid>
        <KpiCard title="Audit readiness" value={`${formatQty(d.score_pct, 0)}%`} icon={ShieldCheck} tone="indigo" caption="Compliant clauses ÷ applicable" />
        <KpiCard title="Open NCRs" value={d.open_ncrs} icon={AlertTriangle} tone={d.open_ncrs ? "danger" : "success"} caption={<button type="button" className="text-link" onClick={() => onGo("ncr")}>Review NCRs</button>} />
        <KpiCard title="Expired instruments" value={d.expired_instruments} icon={Gauge} tone={d.expired_instruments ? "danger" : "success"} caption={<button type="button" className="text-link" onClick={() => onGo("calibration")}>Calibration register</button>} />
      </KpiGrid>
      <section aria-label="Readiness by clause" className="flex flex-col gap-2">
        <h3 className="m-0 text-[13.5px] font-semibold text-fg">By clause</h3>
        {d.by_clause.map((c) => (
          <button key={c.clause} type="button" onClick={() => onGo("checklist")} className="grid grid-cols-[56px_1fr_minmax(120px,220px)_70px] items-center gap-3 rounded-lg px-2 py-1.5 text-left text-[13px] hover:bg-subtle">
            <span className="font-semibold text-fg">{c.clause}</span>
            <span className="truncate text-fg-2">{c.title}</span>
            <Progress value={Number(c.score_pct)} tone="bg-indigo" label={`Clause ${c.clause}`} />
            <span className="tabular text-right text-xs text-fg-muted">{c.compliant}/{c.total}</span>
          </button>
        ))}
      </section>
    </div>
  );
}
