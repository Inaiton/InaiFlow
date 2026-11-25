"use client";

import { useState } from "react";
import { Badge, Button, DecimalInput, NativeSelect } from "@/components/ui";
import { isZero } from "@/core/money";
import { inr } from "../../lib/format";
import { useLedgers } from "../../masters/api";
import { useTdsCompute, useTdsSections } from "../../taxation/api";

/**
 * TDS helper for purchase/payment: pick a section, compute via /taxation/tds/compute, then apply as a CR TDS Payable line.
 * `apply(null)` removes it.
 */
export function TdsHelper({ partyLedgerId, amount, date, applied, apply }: {
  partyLedgerId: string | null; amount: string; date: string; applied: { section: string; amount: string } | null; apply: (t: { section: string; amount: string; ledger_id: string } | null) => void;
}) {
  const sections = useTdsSections(date);
  const tdsLedgers = useLedgers({ q: "TDS", limit: 50, offset: 0 });
  const tdsLedger = tdsLedgers.data?.items.find((l) => l.system_code === "TDS_PAYABLE") ?? tdsLedgers.data?.items.find((l) => l.tax_config?.tax_type === "TDS");
  const compute = useTdsCompute();
  const [section, setSection] = useState(applied?.section ?? "");
  const [manual, setManual] = useState<string>(applied?.amount ?? "");
  const result = compute.data;
  const run = () => partyLedgerId && section && !isZero(amount || "0") && compute.mutate({ section, party_ledger_id: partyLedgerId, amount, voucher_date: date }, { onSuccess: (r) => setManual(r.tds_amount) });
  return (
    <div className="flex flex-wrap items-center gap-2 px-3 py-2 text-[12.5px]">
      <span className="font-medium text-fg-2">TDS</span>
      <NativeSelect aria-label="TDS section" value={section} onChange={(e) => setSection(e.target.value)} className="h-8 w-64 text-[12.5px]">
        <option value="">Not applicable</option>
        {(sections.data ?? []).map((s) => <option key={s.section} value={s.section}>{s.section} · {s.nature}</option>)}
      </NativeSelect>
      <Button size="sm" variant="secondary" disabled={!section || !partyLedgerId} loading={compute.isPending} onClick={run}>Compute</Button>
      {result ? (
        <span className="text-fg-muted">
          {result.applicable ? `${result.rate}% → ${inr(result.tds_amount)}` : "Below threshold"} · {result.threshold_info}{result.pan_available ? "" : " · no PAN (higher rate)"}
        </span>
      ) : null}
      {section ? <DecimalInput aria-label="TDS amount" value={manual} onValueChange={(v) => setManual(v ?? "")} className="h-8 w-32" /> : null}
      {section ? (
        <Button size="sm" variant="secondary" disabled={!tdsLedger || !manual} onClick={() => tdsLedger && apply({ section, amount: manual, ledger_id: tdsLedger.id })}>Apply TDS</Button>
      ) : null}
      {applied ? (
        <>
          <Badge tone="indigo">{applied.section} · {inr(applied.amount)} deducted</Badge>
          <Button size="sm" variant="ghost" onClick={() => { apply(null); setSection(""); setManual(""); }}>Remove</Button>
        </>
      ) : null}
      {section && !tdsLedger && !tdsLedgers.isPending ? <span className="text-warning-text">No “TDS Payable” ledger found</span> : null}
    </div>
  );
}
