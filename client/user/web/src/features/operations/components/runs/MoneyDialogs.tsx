"use client";

import { useState } from "react";
import { Button, Combobox, DatePicker, DecimalInput, Dialog, DialogContent, Field, FieldRow, Hint, Input, NativeSelect, Segmented } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { todayIso } from "@/core/dates";
import { formatMoney, isZero } from "@/core/money";
import { useLedgerLookup, useVoucherLookup } from "../../api/lookups";
import { useLinkVoucher, usePostToRun } from "../../api/runs";

type Run = Schemas["RunOut"];
type DialogProps = { open: boolean; onOpenChange: (o: boolean) => void; run: Run };

function LedgerPicker({ value, onChange, placeholder }: { value: string | null; onChange: (v: string) => void; placeholder: string }) {
  const [q, setQ] = useState("");
  const ledgers = useLedgerLookup(q);
  return (
    <Combobox value={value} onValueChange={onChange} onSearch={setQ} loading={ledgers.isFetching && !ledgers.data} placeholder={placeholder}
      options={(ledgers.data?.items ?? []).map((l) => ({ value: l.id, label: l.name, hint: l.group_name }))} />
  );
}

function StepSelect({ run, value, onChange }: { run: Run; value: string; onChange: (v: string) => void }) {
  return (
    <NativeSelect value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Whole run</option>
      {run.steps.map((s) => <option key={s.id} value={s.id}>{s.step_name}</option>)}
    </NativeSelect>
  );
}

/** Post a direct expense (Dr) or credit (Cr) from the run page → balanced voucher in Accounts (design Ops-Run-DrCr). */
export function PostingDialog({ open, onOpenChange, run }: DialogProps) {
  const post = usePostToRun(run.id);
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [type, setType] = useState<"DR" | "CR">("DR");
  const [amount, setAmount] = useState<string | null>(null);
  const [ledger, setLedger] = useState<string | null>(null);
  const [contra, setContra] = useState<string | null>(null);
  const [date, setDate] = useState(todayIso());
  const [narration, setNarration] = useState("");
  const [stepId, setStepId] = useState("");
  const ready = Boolean(amount && !isZero(amount) && ledger && contra && ledger !== contra && date);
  const submit = async () => {
    await post.mutateAsync({ key, body: { entry_type: type, amount: amount!, ledger_id: ledger!, contra_ledger_id: contra!, voucher_date: date, narration: narration || null, step_id: stepId || null } });
    setKey(crypto.randomUUID());
    setAmount(null);
    setNarration("");
    onOpenChange(false);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Post to this run" description="Creates a balanced journal voucher in Accounts, tagged to this run’s cost centre."
        footer={<><Button onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="primary" disabled={!ready} loading={post.isPending} onClick={() => void submit()}>Post {amount ? formatMoney(amount) : ""}</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Segmented aria-label="Entry type" value={type} onChange={setType} options={[{ value: "DR", label: "Expense (Dr)" }, { value: "CR", label: "Credit (Cr)" }]} />
          <Hint tone="sky">{type === "DR" ? "Adds cost to the run, e.g. coating job work paid in cash." : "Reduces run cost, e.g. scrap sold."}</Hint>
          <FieldRow>
            <Field label="Amount" required><DecimalInput prefix="₹" value={amount} onValueChange={setAmount} /></Field>
            <Field label="Date" required><DatePicker value={date} onValueChange={(v) => setDate(v ?? "")} /></Field>
          </FieldRow>
          <Field label={type === "DR" ? "Expense ledger" : "Income / recovery ledger"} required><LedgerPicker value={ledger} onChange={setLedger} placeholder="Direct expenses" /></Field>
          <Field label={type === "DR" ? "Paid from" : "Received into"} required error={ledger && contra && ledger === contra ? "Pick a different ledger" : undefined}>
            <LedgerPicker value={contra} onChange={setContra} placeholder="Cash / bank / party" />
          </Field>
          <FieldRow>
            <Field label="Step"><StepSelect run={run} value={stepId} onChange={setStepId} /></Field>
            <Field label="Narration"><Input value={narration} onChange={(e) => setNarration(e.target.value)} /></Field>
          </FieldRow>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Link an existing purchase / job-work / sales voucher to the run or one of its steps (design Ops-Run-LinkVoucher). */
export function LinkVoucherDialog({ open, onOpenChange, run }: DialogProps) {
  const link = useLinkVoucher(run.id);
  const [q, setQ] = useState("");
  const vouchers = useVoucherLookup(q, open);
  const [voucherId, setVoucherId] = useState<string | null>(null);
  const [stepId, setStepId] = useState("");
  const submit = async () => {
    await link.mutateAsync({ voucher_id: voucherId!, step_id: stepId || null });
    setVoucherId(null);
    onOpenChange(false);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Link a voucher" description="Search vouchers already entered in Accounts."
        footer={<><Button onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="primary" disabled={!voucherId} loading={link.isPending} onClick={() => void submit()}>Link voucher</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Field label="Voucher" required>
            <Combobox value={voucherId} onValueChange={setVoucherId} onSearch={setQ} loading={vouchers.isFetching && !vouchers.data} placeholder="Search by number or party"
              options={(vouchers.data?.items ?? []).map((v) => ({ value: v.id, label: `${v.voucher_type_name} ${v.voucher_number} · ${formatMoney(v.total_amount)}`, hint: `${v.party_name ?? "—"} · ${v.voucher_date}${v.linked_period_run_id ? " · already linked to a run" : ""}` }))} />
          </Field>
          <Field label="Step"><StepSelect run={run} value={stepId} onChange={setStepId} /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}
