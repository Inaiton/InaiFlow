"use client";

import { Controller } from "react-hook-form";
import { Button, DecimalInput, Dialog, DialogContent, Field, FieldRow, Input, NativeSelect } from "@/components/ui";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { useSaveStockItem, type StockItem } from "../inventory/api";
import { emptyItem, itemSchema, toItemIn } from "../inventory/item-schema";
import { useDialogGuard } from "./dialog-guard";
import { GST_RATES, UOMS } from "./Selects";

/** Alt+C on an item line — create a stock item inline. */
export function QuickItemDialog({ open, name, onClose, onCreated }: { open: boolean; name: string; onClose: () => void; onCreated: (i: StockItem) => void }) {
  return <Dialog open={open} onOpenChange={(o) => !o && onClose()}>{open ? <Body name={name} onClose={onClose} onCreated={onCreated} /> : null}</Dialog>;
}

function Body({ name, onClose, onCreated }: { name: string; onClose: () => void; onCreated: (i: StockItem) => void }) {
  useDialogGuard();
  const save = useSaveStockItem();
  const form = useZodForm(itemSchema, { defaultValues: emptyItem(name) });
  const { register, control, formState: { errors } } = form;
  const submit = form.handleSubmit(async (v) => {
    try {
      onCreated(await save.mutateAsync({ body: toItemIn(v) }));
    } catch (e) {
      applyServerErrors(form, e);
    }
  });
  return (
    <DialogContent title="Create stock item" size="md" description="Opening stock, BOM and drawings can be added later in Inventory"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => void submit()}>Create item</Button></>}>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.stopPropagation(); void submit(e); }} noValidate>
        <Field label="Name" required error={errors.name?.message}><Input autoFocus {...register("name")} /></Field>
        <FieldRow>
          <Field label="Unit"><NativeSelect {...register("uom_primary")}>{UOMS.map((u) => <option key={u}>{u}</option>)}</NativeSelect></Field>
          <Field label="HSN/SAC" error={errors.hsn_sac_code?.message}><Input {...register("hsn_sac_code")} /></Field>
        </FieldRow>
        <FieldRow>
          <Field label="GST rate"><NativeSelect {...register("gst_rate")}>{GST_RATES.map((g) => <option key={g} value={g}>{g}%</option>)}</NativeSelect></Field>
          <Field label="Standard rate"><Controller control={control} name="opening_rate" render={({ field }) => <DecimalInput value={field.value} onValueChange={(v) => field.onChange(v ?? "")} prefix="₹" />} /></Field>
        </FieldRow>
        <button type="submit" hidden />
      </form>
    </DialogContent>
  );
}
