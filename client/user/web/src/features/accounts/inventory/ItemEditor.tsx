"use client";

import { Trash2, Upload } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Controller, useFieldArray } from "react-hook-form";
import { toast } from "sonner";
import { Button, Card, DecimalInput, ErrorState, Field, FieldRow, Input, NativeSelect, PageHeader, Section, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { useShortcutScope } from "@/core/shortcuts/registry";
import { validateFile } from "@/core/upload";
import { GST_RATES, UOMS } from "../components/Selects";
import { StockItemPicker } from "../components/StockItemPicker";
import { useAccHref } from "../lib/api-base";
import { useRBar } from "../shell/rbar-context";
import { useSaveStockItem, useStockGroups, useStockItem, useUploadDiagram, type StockItem } from "./api";
import { emptyItem, fromItem, itemSchema, toItemIn, VALUATION_METHODS, type ItemForm } from "./item-schema";

const DIAGRAM_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/webp"];

function Editor({ initial, item }: { initial: ItemForm; item?: StockItem }) {
  useShortcutScope("master");
  const router = useRouter();
  const href = useAccHref();
  const groups = useStockGroups();
  const save = useSaveStockItem();
  const upload = useUploadDiagram();
  const form = useZodForm(itemSchema, { defaultValues: initial });
  const { register, control, setValue, watch, formState: { errors } } = form;
  const custom = useFieldArray({ control, name: "custom_fields" });
  const bom = useFieldArray({ control, name: "bom" });
  const back = () => router.push(item ? href(`/inventory/items/${item.id}`) : href("/inventory/items"));
  const submit = form.handleSubmit(async (v) => {
    try {
      const out = await save.mutateAsync({ id: item?.id, body: toItemIn(v) });
      router.push(href(`/inventory/items/${out.id}`));
    } catch (e) {
      applyServerErrors(form, e);
    }
  });
  useRBar([{ id: "accept", combo: "ctrl+a", label: "Accept", run: () => void submit() }, { id: "quit", combo: "escape", label: "Quit", run: back }], "master");
  const onDiagram = async (file: File | undefined) => {
    if (!file) return;
    const err = validateFile(file, { types: DIAGRAM_TYPES });
    if (err) return toast.error(err);
    const key = await upload.mutateAsync(file);
    setValue("diagram_storage_key", key);
    toast.success("Drawing uploaded — save the item to keep it");
  };
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Stock items", href: href("/inventory/items") }, { label: item?.name ?? "New item" }]}
        title={item ? "Alter stock item" : "Create stock item"} description="Synced with Operations items · Ctrl A to save"
        actions={<><Button variant="ghost" onClick={back}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => void submit()}>Save item</Button></>} />
      <Card>
        <form className="flex flex-col gap-5" onSubmit={submit} noValidate>
          <Section title="Basic">
            <div className="flex flex-col gap-3">
              <FieldRow>
                <Field label="Item name" required error={errors.name?.message}><Input autoFocus {...register("name")} /></Field>
                <Field label="Part no. / SKU"><Input {...register("sku_code")} /></Field>
              </FieldRow>
              <FieldRow>
                <Field label="Stock group"><NativeSelect {...register("stock_group_id")}><option value="">Primary</option>{(groups.data ?? []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</NativeSelect></Field>
                <Field label="Type"><NativeSelect {...register("target_type")}><option value="STOCK_ITEM">Stock item</option><option value="STANDALONE_PROCESS">Standalone process (service, maintenance)</option></NativeSelect></Field>
              </FieldRow>
            </div>
          </Section>
          <Section title="Units & valuation">
            <FieldRow>
              <Field label="Primary unit"><NativeSelect {...register("uom_primary")}>{UOMS.map((u) => <option key={u}>{u}</option>)}</NativeSelect></Field>
              <Field label="Alternate unit"><NativeSelect {...register("uom_alternate")}><option value="">None</option>{UOMS.map((u) => <option key={u}>{u}</option>)}</NativeSelect></Field>
              <Field label="Conversion (primary per alternate)" error={errors.uom_conversion_factor?.message}><Input inputMode="decimal" disabled={!watch("uom_alternate")} {...register("uom_conversion_factor")} /></Field>
              <Field label="Valuation method"><NativeSelect {...register("valuation_method")}>{VALUATION_METHODS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}</NativeSelect></Field>
            </FieldRow>
          </Section>
          <Section title="Statutory & reorder">
            <FieldRow>
              <Field label="HSN / SAC" error={errors.hsn_sac_code?.message}><Input {...register("hsn_sac_code")} /></Field>
              <Field label="GST rate"><NativeSelect {...register("gst_rate")}>{GST_RATES.map((g) => <option key={g} value={g}>{g}%</option>)}</NativeSelect></Field>
              <Field label="Reorder level" error={errors.reorder_level?.message}><Input inputMode="decimal" {...register("reorder_level")} /></Field>
            </FieldRow>
          </Section>
          <Section title="Opening stock" description="Valued at the opening rate (also the standard cost)">
            <FieldRow>
              <Field label="Quantity" error={errors.opening_qty?.message}><Input inputMode="decimal" {...register("opening_qty")} /></Field>
              <Field label="Rate" error={errors.opening_rate?.message}><Controller control={control} name="opening_rate" render={({ field }) => <DecimalInput decimals={4} value={field.value} onValueChange={(v) => field.onChange(v ?? "")} prefix="₹" />} /></Field>
            </FieldRow>
          </Section>
          <Section title="Bill of materials" description="Components consumed per unit produced (used by the Manufacturing Journal)">
            <div className="flex flex-col gap-2">
              {bom.fields.map((f, i) => (
                <div key={f.id} className="grid grid-cols-[minmax(0,1fr)_140px_120px_36px] items-center gap-2">
                  <div className="rounded-lg border border-line"><Controller control={control} name={`bom.${i}.raw_item_id`} render={({ field }) => <StockItemPicker value={field.value || null} onChange={(it) => field.onChange(it.id)} placeholder="Component" />} /></div>
                  <Input inputMode="decimal" aria-label="Qty per unit" placeholder="Qty / unit" {...register(`bom.${i}.qty_per_unit`)} />
                  <Input inputMode="decimal" aria-label="Scrap %" placeholder="Scrap %" {...register(`bom.${i}.scrap_pct`)} />
                  <Button size="icon" variant="ghost" aria-label="Remove component" onClick={() => bom.remove(i)}><Trash2 /></Button>
                </div>
              ))}
              <Button size="sm" variant="ghost" className="self-start" onClick={() => bom.append({ raw_item_id: "", qty_per_unit: "", scrap_pct: "" })}>+ Add component</Button>
            </div>
          </Section>
          <Section title="Custom fields" description="Material grade, hardness, drawing rev…">
            <div className="flex flex-col gap-2">
              {custom.fields.map((f, i) => (
                <div key={f.id} className="grid grid-cols-[220px_minmax(0,1fr)_36px] gap-2">
                  <Input aria-label="Field name" placeholder="Field" {...register(`custom_fields.${i}.key`)} />
                  <Input aria-label="Value" placeholder="Value" {...register(`custom_fields.${i}.value`)} />
                  <Button size="icon" variant="ghost" aria-label="Remove field" onClick={() => custom.remove(i)}><Trash2 /></Button>
                </div>
              ))}
              <Button size="sm" variant="ghost" className="self-start" onClick={() => custom.append({ key: "", value: "" })}>+ Add field</Button>
            </div>
          </Section>
          <Section title="Engineering drawing">
            <label className="flex w-fit cursor-pointer items-center gap-2 rounded-lg border border-dashed border-line-strong px-3 py-2 text-[12.5px] text-fg-3 hover:bg-subtle">
              <Upload className="size-4" aria-hidden />{watch("diagram_storage_key") ? "Drawing ready — will be saved" : item?.diagram_url ? "Replace drawing" : "Upload drawing (PDF / image)"}
              <input type="file" className="sr-only" accept={DIAGRAM_TYPES.join(",")} onChange={(e) => void onDiagram(e.target.files?.[0])} />
            </label>
          </Section>
          <button type="submit" hidden />
        </form>
      </Card>
    </>
  );
}

/** /accounts/inventory/items/new and /[id]/edit (design: Acc-I-ItemNew, Acc-I-BOM). */
export function ItemEditor({ id }: { id?: string }) {
  const params = useSearchParams();
  const q = useStockItem(id);
  if (!id) return <Editor initial={emptyItem(params.get("name") ?? "")} />;
  if (q.isPending) return <Skeleton className="h-96 w-full" />;
  if (q.isError) return <ErrorState message={describeError(q.error)} onRetry={() => void q.refetch()} />;
  return <Editor key={q.data.id} initial={fromItem(q.data)} item={q.data} />;
}
