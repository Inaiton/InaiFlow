"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, DatePicker, DecimalInput, Dialog, DialogContent, Field, Input, NativeSelect } from "@/components/ui";
import { CostCentreSelect } from "../../components/Selects";
import { useDialogGuard } from "../../components/dialog-guard";
import { accDate, amt, drcr } from "../../lib/format";
import { billAllocationsValid, billRemaining } from "../../lib/voucher-math";
import { useOutstandingBills } from "../../masters/api";
import type { BillAllocation } from "./draft";

interface RowLike { ledger_id: string | null; amount: string; bills: BillAllocation[]; cost_centre_id?: string | null }

/** Bill-wise allocation popup (design: Acc-V-BillRef): New ref / Against ref (from outstanding bills) / Advance / On account. */
export function BillAllocDialog({ row, onClose, onSave }: { row: RowLike | null; onClose: () => void; onSave: (b: BillAllocation[]) => void }) {
  return <Dialog open={Boolean(row)} onOpenChange={(o) => !o && onClose()}>{row ? <BillBody row={row} onClose={onClose} onSave={onSave} /> : null}</Dialog>;
}

function BillBody({ row, onClose, onSave }: { row: RowLike; onClose: () => void; onSave: (b: BillAllocation[]) => void }) {
  useDialogGuard();
  const outstanding = useOutstandingBills(row.ledger_id);
  const [list, setList] = useState<BillAllocation[]>(row.bills.length ? row.bills : [{ ref_type: "NEW_REF", ref_name: "", amount: row.amount, due_date: null }]);
  const upd = (i: number, p: Partial<BillAllocation>) => setList((l) => l.map((b, j) => (j === i ? { ...b, ...p } : b)));
  const remaining = billRemaining(row.amount, list);
  const valid = billAllocationsValid(row.amount, list);
  return (
    <DialogContent
      title="Bill-wise details"
      description={`Allocate ${amt(row.amount)} · remaining ${amt(remaining)}`}
      size="lg"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!valid} onClick={() => onSave(list)}>Accept</Button></>}
    >
      <div className="flex flex-col gap-2">
        {list.map((b, i) => (
          <div key={i} className="grid grid-cols-[130px_minmax(0,1fr)_150px_150px_36px] items-end gap-2">
            <Field label="Type"><NativeSelect value={b.ref_type} onChange={(e) => upd(i, { ref_type: e.target.value as BillAllocation["ref_type"] })}>
              <option value="NEW_REF">New ref</option><option value="AGAINST_REF">Against ref</option><option value="ADVANCE">Advance</option><option value="ON_ACCOUNT">On account</option>
            </NativeSelect></Field>
            <Field label="Reference">
              {b.ref_type === "AGAINST_REF" ? (
                <NativeSelect value={b.ref_name} onChange={(e) => {
                  const bill = outstanding.data?.find((x) => x.ref_name === e.target.value);
                  upd(i, { ref_name: e.target.value, ...(bill ? { amount: bill.pending, due_date: bill.due_date } : {}) });
                }}>
                  <option value="">{outstanding.isPending ? "Loading bills…" : "Pick a pending bill"}</option>
                  {(outstanding.data ?? []).map((x) => <option key={x.ref_name} value={x.ref_name}>{x.ref_name} · {accDate(x.bill_date)} · {drcr(x.pending, x.pending_type)}</option>)}
                </NativeSelect>
              ) : <Input value={b.ref_name} onChange={(e) => upd(i, { ref_name: e.target.value })} placeholder={b.ref_type === "ON_ACCOUNT" ? "On account" : "Bill no."} />}
            </Field>
            <Field label="Due date"><DatePicker value={b.due_date ?? null} onValueChange={(v) => upd(i, { due_date: v })} /></Field>
            <Field label="Amount"><DecimalInput value={b.amount} onValueChange={(v) => upd(i, { amount: v ?? "" })} /></Field>
            <Button size="icon" variant="ghost" aria-label="Remove allocation" onClick={() => setList((l) => l.filter((_, j) => j !== i))}><Trash2 /></Button>
          </div>
        ))}
        <div className="flex items-center justify-between">
          <Button size="sm" variant="ghost" onClick={() => setList((l) => [...l, { ref_type: "AGAINST_REF", ref_name: "", amount: remaining, due_date: null }])}>+ Add reference</Button>
          {valid ? <Badge tone="success">Allocated</Badge> : <Badge tone="warning">Every reference needs a name and amount; Σ ≤ line amount</Badge>}
        </div>
      </div>
    </DialogContent>
  );
}

export function CostCentreDialog({ row, onClose, onSave }: { row: RowLike | null; onClose: () => void; onSave: (id: string | null) => void }) {
  return <Dialog open={Boolean(row)} onOpenChange={(o) => !o && onClose()}>{row ? <CcBody row={row} onClose={onClose} onSave={onSave} /> : null}</Dialog>;
}

function CcBody({ row, onClose, onSave }: { row: RowLike; onClose: () => void; onSave: (id: string | null) => void }) {
  useDialogGuard();
  const [id, setId] = useState(row.cost_centre_id ?? "");
  return (
    <DialogContent title="Cost centre allocation" description={`Tag ${amt(row.amount)} to a cost centre (period runs appear as cost centres)`} size="sm"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" onClick={() => onSave(id || null)}>Accept</Button></>}>
      <Field label="Cost centre"><CostCentreSelect value={id} onValueChange={setId} /></Field>
    </DialogContent>
  );
}
