"use client";

import { Trash2 } from "lucide-react";
import { Button, DecimalInput, Input, NativeSelect } from "@/components/ui";
import { Amt } from "../../components/Amount";
import { LedgerPicker } from "../../components/LedgerPicker";
import { GodownSelect, GST_RATES } from "../../components/Selects";
import { StockItemPicker } from "../../components/StockItemPicker";
import { invoiceSubtotal } from "../../lib/voucher-math";
import type { Action, Draft, ItemRow } from "./draft";

const cols = "grid grid-cols-[22px_minmax(180px,1fr)_74px_120px_88px_96px_56px_60px_70px_118px_32px] items-center gap-x-1.5";
const cell = "h-9 rounded-md border-transparent bg-transparent px-1.5 hover:border-line focus:bg-surface";

/** Item lines of an invoice / order (Name of item, HSN, godown, qty, rate, per, disc %, GST %, amount). */
export function InvoiceItems({ draft, dispatch, defaultGodown, onCreateItem, onCreateLedger }: {
  draft: Draft; dispatch: (a: Action) => void; defaultGodown: string; onCreateItem: (name: string, rowKey: string) => void; onCreateLedger: (name: string, rowKey: string) => void;
}) {
  const set = (key: string, patch: Partial<ItemRow>) => dispatch({ type: "item", key, patch });
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[980px]">
        <div className={`${cols} border-b border-line px-3 py-2 text-[11px] font-semibold tracking-wide text-fg-muted uppercase`}>
          <span>#</span><span>Name of item</span><span>HSN</span><span>Godown</span><span className="text-right">Quantity</span><span className="text-right">Rate</span><span>Per</span>
          <span className="text-right">Disc %</span><span>GST %</span><span className="text-right">Amount</span><span />
        </div>
        {draft.items.map((r, i) => (
          <div key={r.key} className={`${cols} border-b border-line/70 px-3 py-1`}>
            <span className="text-[12px] text-fg-muted">{i + 1}</span>
            {r.kind === "item" ? (
              <StockItemPicker
                value={r.stock_item_id}
                onChange={(it) => set(r.key, { stock_item_id: it.id, uom: it.uom_primary, hsn: it.hsn_sac_code ?? "", gst_rate: it.gst_rate, rate: r.rate || it.opening_rate || "", godown_id: r.godown_id || defaultGodown })}
                onCreate={(name) => onCreateItem(name, r.key)}
              />
            ) : (
              <LedgerPicker value={r.ledger_id} placeholder="Charges ledger (freight, packing…)" onChange={(l) => set(r.key, { ledger_id: l.id, gst_rate: l.tax_config?.rate ?? r.gst_rate })} onCreate={(name) => onCreateLedger(name, r.key)} />
            )}
            <Input data-nav="" aria-label="HSN/SAC" value={r.hsn} onChange={(e) => set(r.key, { hsn: e.target.value })} className={cell} />
            {r.kind === "item" ? <GodownSelect value={r.godown_id} onValueChange={(v) => set(r.key, { godown_id: v })} className="h-9 px-1 text-[12.5px]" aria-label="Godown" /> : <span className="text-[12px] text-fg-faint">—</span>}
            {r.kind === "item" ? (
              <>
                <DecimalInput data-nav="" aria-label="Quantity" kind="qty" decimals={4} placeholder="0" value={r.qty} onValueChange={(v) => set(r.key, { qty: v ?? "" })} className={cell} />
                <DecimalInput data-nav="" aria-label="Rate" decimals={4} value={r.rate} onValueChange={(v) => set(r.key, { rate: v ?? "" })} className={cell} />
                <span className="text-[12.5px] text-fg-muted">{r.uom}</span>
                <DecimalInput data-nav="" aria-label="Discount %" placeholder="0" value={r.disc} onValueChange={(v) => set(r.key, { disc: v ?? "" })} className={cell} />
              </>
            ) : <><span /><span /><span /><span /></>}
            <NativeSelect aria-label="GST rate" value={r.gst_rate ? String(Number(r.gst_rate)) : ""} onChange={(e) => set(r.key, { gst_rate: e.target.value })} className="h-9 px-1 text-[12.5px]">
              <option value="">—</option>{GST_RATES.map((g) => <option key={g} value={g}>{g}%</option>)}
            </NativeSelect>
            {r.kind === "item" ? (
              <Amt v={r.amount} className="pr-1.5 text-right text-[13px]" />
            ) : (
              <DecimalInput data-nav="" aria-label="Amount" value={r.amount} onValueChange={(v) => set(r.key, { amount: v ?? "" })} className={cell} />
            )}
            <Button size="icon-sm" variant="ghost" aria-label="Remove line" onClick={() => dispatch({ type: "item-remove", key: r.key })}><Trash2 /></Button>
            {r.kind === "item" && r.stock_item_id ? (
              <div className="col-span-full -mt-0.5 flex items-center gap-2 pb-1 pl-7 text-[11.5px] text-fg-muted">
                Batch <Input aria-label="Batch number" value={r.batch} onChange={(e) => set(r.key, { batch: e.target.value })} className="h-7 w-40 text-[12px]" />
              </div>
            ) : null}
          </div>
        ))}
        <div className="flex items-center justify-between px-3 py-2">
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => dispatch({ type: "item-add", godown_id: defaultGodown })}>+ Add item</Button>
            <Button size="sm" variant="ghost" onClick={() => dispatch({ type: "item-add", kind: "ledger" })}>+ Add charges ledger</Button>
          </div>
          <span className="flex items-center gap-3 text-[12.5px] text-fg-muted">Alt C to create a new item <span className="font-semibold text-fg">Subtotal <Amt v={invoiceSubtotal(draft.items)} strong /></span></span>
        </div>
      </div>
    </div>
  );
}
