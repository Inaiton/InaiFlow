"use client";

import { DatePicker, Field, Input, SwitchRow } from "@/components/ui";
import { LedgerPicker } from "../../components/LedgerPicker";
import { StateSelect } from "../../components/Selects";
import { drcr } from "../../lib/format";
import type { VoucherKind } from "../../lib/voucher-kinds";
import { useLedger } from "../../masters/api";
import type { Action, Draft } from "./draft";

/** Party A/c name, sales/purchase ledger, place of supply and supplier bill details (bill-style header). */
export function InvoiceHeader({ draft, dispatch, kind, onCreateLedger }: { draft: Draft; dispatch: (a: Action) => void; kind: VoucherKind; onCreateLedger: (name: string, target: "party" | "ledger") => void }) {
  const party = useLedger(draft.party_ledger_id);
  const ledger = useLedger(draft.ledger_id);
  const set = (patch: Partial<Draft>) => dispatch({ type: "set", patch });
  const p = party.data;
  const supplierSide = kind.ledgerKind === "purchase";
  return (
    <div className="grid gap-3 p-3 md:grid-cols-2">
      <div className="flex flex-col gap-2">
        <label className="grid grid-cols-[130px_minmax(0,1fr)] items-center gap-2 text-[13px]">
          <span className="text-fg-muted">Party A/c name</span>
          <LedgerPicker value={draft.party_ledger_id} autoFocus filter={{ party_only: true }} aria-label="Party ledger"
            onChange={(l) => set({
              party_ledger_id: l.id, party_bill_wise: l.maintain_bill_by_bill, party_bills: [],
              pos_state: draft.is_export ? draft.pos_state : (l.party_details?.state_code ?? ""), is_sez: Boolean(l.party_details?.is_sez),
            })}
            onCreate={() => onCreateLedger("", "party")} />
        </label>
        {p ? (
          <p className="pl-[138px] text-[12px] text-fg-muted">
            Current balance <span className="font-medium text-fg">{drcr(p.closing_balance, p.closing_balance_type)}</span>
            {p.party_details?.gstin ? ` · GSTIN ${p.party_details.gstin}` : " · Unregistered"}
            {p.credit_limit ? ` · Credit limit ${drcr(p.credit_limit, null)}` : ""}{p.default_credit_days ? ` · ${p.default_credit_days} days` : ""}
          </p>
        ) : null}
        {!kind.order ? (
          <>
            <label className="grid grid-cols-[130px_minmax(0,1fr)] items-center gap-2 text-[13px]">
              <span className="text-fg-muted">{kind.ledgerKind === "sales" ? "Sales ledger" : "Purchase ledger"}</span>
              <LedgerPicker value={draft.ledger_id} aria-label="Sales or purchase ledger" filter={{ nature: kind.ledgerKind === "sales" ? "INCOME" : "EXPENSES" }}
                onChange={(l) => set({ ledger_id: l.id })} onCreate={() => onCreateLedger("", "ledger")} />
            </label>
            {ledger.data ? <p className="pl-[138px] text-[12px] text-fg-muted">Current balance <span className="font-medium text-fg">{drcr(ledger.data.closing_balance, ledger.data.closing_balance_type)}</span></p> : null}
          </>
        ) : null}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {supplierSide ? (
          <>
            <Field label="Supplier invoice no."><Input data-nav="" value={draft.supplier_invoice_no} onChange={(e) => set({ supplier_invoice_no: e.target.value })} /></Field>
            <Field label="Invoice date"><DatePicker value={draft.supplier_invoice_date || null} onValueChange={(v) => set({ supplier_invoice_date: v ?? "" })} /></Field>
          </>
        ) : (
          <Field label="Buyer’s order no. / reference" className="col-span-2"><Input data-nav="" value={draft.supplier_invoice_no} onChange={(e) => set({ supplier_invoice_no: e.target.value })} /></Field>
        )}
        <Field label="Place of supply" className="col-span-2"><StateSelect value={draft.pos_state} onValueChange={(v) => set({ pos_state: v })} placeholder="Party state" /></Field>
        {!kind.order ? (
          <details className="col-span-2 rounded-lg border border-line px-3 py-1.5 text-[12.5px]">
            <summary className="cursor-pointer text-fg-3">GST options (reverse charge, export, SEZ)</summary>
            <div className="mt-2 flex flex-col gap-2">
              <SwitchRow label="Reverse charge (RCM)" checked={draft.reverse_charge} onCheckedChange={(v) => set({ reverse_charge: v })} />
              <SwitchRow label="Export" description="IGST / LUT" checked={draft.is_export} onCheckedChange={(v) => set({ is_export: v })} />
              <SwitchRow label="SEZ supply" checked={draft.is_sez} onCheckedChange={(v) => set({ is_sez: v })} />
            </div>
          </details>
        ) : null}
      </div>
    </div>
  );
}
