"use client";

import { FileStack, Split, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, DatePicker, DecimalInput, Input } from "@/components/ui";
import { cn } from "@/lib/utils";
import { Amt } from "../../components/Amount";
import { LedgerPicker } from "../../components/LedgerPicker";
import { amt } from "../../lib/format";
import { lineageCodes } from "../../lib/group-tree";
import type { VoucherKind } from "../../lib/voucher-kinds";
import { absDiff } from "../../lib/voucher-math";
import { useGroups } from "../../masters/api";
import { BillAllocDialog, CostCentreDialog } from "./AllocationDialogs";
import { accTotals, type AccRow, type Action, type Draft } from "./draft";

const cell = "h-9 rounded-md border-transparent bg-transparent hover:border-line focus:bg-surface";

/** Dr/Cr double-entry grid (Contra, Payment, Receipt, Journal…). Enter advances; leaving the last amount adds a balancing line. */
export function AccountingGrid({ draft, dispatch, kind, onCreateLedger }: {
  draft: Draft; dispatch: (a: Action) => void; kind: VoucherKind; onCreateLedger: (name: string, rowKey: string) => void;
}) {
  const groups = useGroups();
  const [bills, setBills] = useState<AccRow | null>(null);
  const [cc, setCc] = useState<AccRow | null>(null);
  const t = accTotals(draft);
  const set = (key: string, patch: Partial<AccRow>) => dispatch({ type: "acc", key, patch });
  return (
    <div className="flex flex-col">
      <div className="grid grid-cols-[56px_minmax(0,1fr)_150px_150px_64px] gap-x-2 border-b border-line px-3 py-2 text-[11px] font-semibold tracking-wide text-fg-muted uppercase">
        <span>Dr / Cr</span><span>Particulars</span><span className="text-right">Debit</span><span className="text-right">Credit</span><span />
      </div>
      {draft.acc.map((r) => (
        <div key={r.key} className="border-b border-line/70 px-3 py-1">
          <div className="grid grid-cols-[56px_minmax(0,1fr)_150px_150px_64px] items-center gap-x-2">
            <select
              data-nav=""
              aria-label="Dr or Cr"
              value={r.side}
              onChange={(e) => set(r.key, { side: e.target.value as AccRow["side"] })}
              onKeyDown={(e) => {
                if (e.key.toLowerCase() === "d") set(r.key, { side: "DR" });
                if (e.key.toLowerCase() === "c" && !e.altKey) set(r.key, { side: "CR" });
              }}
              className="h-9 rounded-md bg-transparent px-1 text-[13px] font-semibold text-fg focus:bg-surface focus:outline-primary"
            >
              <option value="DR">Dr</option><option value="CR">Cr</option>
            </select>
            <LedgerPicker
              value={r.ledger_id}
              aria-label={r.side === "DR" ? "By ledger" : "To ledger"}
              onChange={(l) => {
                const codes = lineageCodes(l.group_id, groups.data ?? []);
                set(r.key, { ledger_id: l.id, bill_wise: l.maintain_bill_by_bill, is_bank: codes.has("BANK_ACCOUNTS") || codes.has("BANK_OD") });
              }}
              onCreate={(name) => onCreateLedger(name, r.key)}
            />
            {(["DR", "CR"] as const).map((side) =>
              side === r.side ? (
                <DecimalInput
                  key={side}
                  data-nav=""
                  aria-label={side === "DR" ? "Debit amount" : "Credit amount"}
                  value={r.amount}
                  onValueChange={(v) => set(r.key, { amount: v ?? "" })}
                  onBlur={() => dispatch({ type: "acc-commit", key: r.key })}
                  className={cell}
                />
              ) : <span key={side} />,
            )}
            <div className="flex justify-end gap-0.5">
              <Button size="icon-sm" variant="ghost" aria-label="Cost centre" title="Cost centre allocation" onClick={() => setCc(r)} className={cn(r.cost_centre_id && "text-indigo")}><Split /></Button>
              <Button size="icon-sm" variant="ghost" aria-label="Remove line" onClick={() => dispatch({ type: "acc-remove", key: r.key })}><Trash2 /></Button>
            </div>
          </div>
          {r.bill_wise || (kind.instrument && r.is_bank) || r.cost_centre_id ? (
            <div className="ml-[64px] flex flex-wrap items-center gap-2 pb-1 text-[12px] text-fg-muted">
              {r.bill_wise ? (
                <button type="button" className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-link hover:bg-subtle" onClick={() => setBills(r)}>
                  <FileStack className="size-3.5" aria-hidden />
                  {r.bills.length ? r.bills.map((b) => `${b.ref_type === "AGAINST_REF" ? "Agst" : b.ref_type === "NEW_REF" ? "New" : b.ref_type === "ADVANCE" ? "Adv" : "On a/c"} ${b.ref_name} ${amt(b.amount)}`).join(" · ") : "Bill-wise details…"}
                </button>
              ) : null}
              {r.cost_centre_id ? <Badge tone="indigo">Cost centre set</Badge> : null}
              {kind.instrument && r.is_bank ? (
                <span className="flex items-center gap-1.5">
                  Inst. no. <Input aria-label="Instrument number" value={r.instrument_no} onChange={(e) => set(r.key, { instrument_no: e.target.value })} className="h-8 w-32" />
                  Date <DatePicker aria-label="Instrument date" value={r.instrument_date || null} onValueChange={(v) => set(r.key, { instrument_date: v ?? "" })} className="h-8 w-40" />
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      ))}
      <div className="flex items-center justify-between px-3 py-1">
        <Button size="sm" variant="ghost" onClick={() => dispatch({ type: "acc-add" })}>+ Add line</Button>
        <span className="text-[11.5px] text-fg-muted">Type D / C to switch side · Alt C creates a ledger</span>
      </div>
      <div className="grid grid-cols-[56px_minmax(0,1fr)_150px_150px_64px] items-center gap-x-2 border-t-2 border-fg px-3 py-2 text-[13px] font-semibold">
        <span /><span className="text-right text-fg-muted">Total</span>
        <Amt v={t.debit} strong className="text-right" /><Amt v={t.credit} strong className="text-right" />
        {t.balanced ? <Badge tone="success">Balanced</Badge> : <Badge tone="danger" title="Debit − credit">Diff {amt(absDiff(t))}</Badge>}
      </div>
      <BillAllocDialog row={bills} onClose={() => setBills(null)} onSave={(b) => { if (bills) set(bills.key, { bills: b }); setBills(null); }} />
      <CostCentreDialog row={cc} onClose={() => setCc(null)} onSave={(id) => { if (cc) set(cc.key, { cost_centre_id: id }); setCc(null); }} />
    </div>
  );
}
