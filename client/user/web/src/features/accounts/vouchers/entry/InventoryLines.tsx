"use client";

import { Trash2 } from "lucide-react";
import { Button, DecimalInput, Input } from "@/components/ui";
import { Amt } from "../../components/Amount";
import { GodownSelect } from "../../components/Selects";
import { StockItemPicker } from "../../components/StockItemPicker";
import { sum } from "@/core/money";
import type { Action, Draft, InvRow } from "./draft";

const cols = "grid grid-cols-[minmax(180px,1fr)_140px_110px_60px_110px_120px_110px_32px] items-center gap-x-1.5";
const cell = "h-9 rounded-md border-transparent bg-transparent px-1.5 hover:border-line focus:bg-surface";

function Side({ title, dir, draft, dispatch, defaultGodown, onCreateItem }: { title: string; dir: InvRow["dir"]; draft: Draft; dispatch: (a: Action) => void; defaultGodown: string; onCreateItem: (name: string, key: string) => void }) {
  const rows = draft.inv.filter((r) => r.dir === dir);
  const set = (key: string, patch: Partial<InvRow>) => dispatch({ type: "inv", key, patch });
  return (
    <section className="flex flex-col">
      <h3 className="bg-subtle px-3 py-1.5 text-[12px] font-semibold text-fg-2">{title}</h3>
      <div className={`${cols} border-b border-line px-3 py-1.5 text-[11px] font-semibold tracking-wide text-fg-muted uppercase`}>
        <span>Item</span><span>Godown</span><span>Batch</span><span>Per</span><span className="text-right">Quantity</span><span className="text-right">Rate</span><span className="text-right">Amount</span><span />
      </div>
      {rows.map((r) => (
        <div key={r.key} className={`${cols} border-b border-line/70 px-3 py-1`}>
          <StockItemPicker value={r.stock_item_id} onChange={(it) => set(r.key, { stock_item_id: it.id, uom: it.uom_primary, rate: r.rate || it.opening_rate, godown_id: r.godown_id || defaultGodown })} onCreate={(n) => onCreateItem(n, r.key)} />
          <GodownSelect value={r.godown_id} onValueChange={(v) => set(r.key, { godown_id: v })} className="h-9 px-1 text-[12.5px]" aria-label="Godown" />
          <Input aria-label="Batch" value={r.batch} onChange={(e) => set(r.key, { batch: e.target.value })} className={cell} />
          <span className="text-[12.5px] text-fg-muted">{r.uom}</span>
          <DecimalInput data-nav="" aria-label="Quantity" kind="qty" decimals={4} placeholder="0" value={r.qty} onValueChange={(v) => set(r.key, { qty: v ?? "" })} className={cell} />
          <DecimalInput data-nav="" aria-label="Rate" decimals={4} value={r.rate} onValueChange={(v) => set(r.key, { rate: v ?? "" })} className={cell} />
          <Amt v={r.amount} className="pr-1.5 text-right" />
          <Button size="icon-sm" variant="ghost" aria-label="Remove line" onClick={() => dispatch({ type: "inv-remove", key: r.key })}><Trash2 /></Button>
        </div>
      ))}
      <div className="flex items-center justify-between px-3 py-1.5">
        <Button size="sm" variant="ghost" onClick={() => dispatch({ type: "inv-add", dir, godown_id: defaultGodown })}>+ Add line</Button>
        <span className="text-[12.5px] text-fg-muted">Total <Amt v={sum(rows.map((r) => r.amount || "0"))} strong /></span>
      </div>
    </section>
  );
}

/** Stock / Manufacturing / Physical stock journal: consumption (source) and production (destination) lines. */
export function InventoryLines({ draft, dispatch, base, defaultGodown, onCreateItem }: { draft: Draft; dispatch: (a: Action) => void; base: string; defaultGodown: string; onCreateItem: (name: string, key: string) => void }) {
  const mfg = base === "MFG_JOURNAL";
  const physical = base === "PHYSICAL_STOCK";
  return (
    <div className="flex flex-col gap-2">
      {physical ? null : <Side title={mfg ? "Components (consumption)" : "Source (consumption)"} dir="OUTWARD" draft={draft} dispatch={dispatch} defaultGodown={defaultGodown} onCreateItem={onCreateItem} />}
      <Side title={physical ? "Counted stock" : mfg ? "Finished goods (production)" : "Destination (production)"} dir="INWARD" draft={draft} dispatch={dispatch} defaultGodown={defaultGodown} onCreateItem={onCreateItem} />
    </div>
  );
}
