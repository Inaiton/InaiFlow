"use client";

import { FileUp, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Controller } from "react-hook-form";
import { z } from "zod";
import {
  AdvancedSection, Button, Card, DecimalInput, Field, FieldRow, Input, NativeSelect, PageHeader, Segmented,
} from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { validateFile } from "@/core/upload";
import { useSaveItem, useUploadDiagram } from "../../api/items";
import { useOpsPath } from "../../paths";
import { CustomFieldsEditor } from "./CustomFieldsEditor";
import { readFields, writeFields, type ItemFieldsValue } from "./item-fields";

const schema = z.object({
  target_type: z.enum(["STOCK_ITEM", "STANDALONE_PROCESS"]),
  name: z.string().trim().min(1, "Give it a name"),
  sku_code: z.string().trim().max(60),
  uom_primary: z.string().trim().min(1, "Unit is required"),
  uom_alternate: z.string().trim(),
  hsn_sac_code: z.string().trim(),
  gst_rate: z.string(),
  valuation_method: z.string(),
  opening_qty: z.string(),
  opening_rate: z.string(),
});
type Values = z.input<typeof schema>;

const DIAGRAM_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/webp"];

/** Create / edit an operations item (design Ops-Item-New): Basics → Drawing → Specs; tax & costing collapsed. */
export function ItemForm({ item }: { item?: Schemas["OpsItemOut"] }) {
  const router = useRouter();
  const p = useOpsPath();
  const save = useSaveItem(item?.id);
  const upload = useUploadDiagram();
  const fileRef = useRef<HTMLInputElement>(null);
  const [diagram, setDiagram] = useState<{ key: string; name: string } | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [fields, setFields] = useState<ItemFieldsValue>(() => readFields(item?.custom_fields));
  const form = useZodForm(schema, {
    defaultValues: {
      target_type: item?.target_type === "STANDALONE_PROCESS" ? "STANDALONE_PROCESS" : "STOCK_ITEM",
      name: item?.name ?? "", sku_code: item?.sku_code ?? "", uom_primary: item?.uom_primary ?? "Nos", uom_alternate: item?.uom_alternate ?? "",
      hsn_sac_code: item?.hsn_sac_code ?? "", gst_rate: item?.gst_rate ?? "18", valuation_method: item?.valuation_method ?? "WEIGHTED_AVG",
      opening_qty: item?.opening_qty ?? "0", opening_rate: item?.opening_rate ?? "0",
    },
  });
  const type = form.watch("target_type");
  const errors = form.formState.errors;
  const spec = (k: string) => fields.values[k] ?? "";
  const setSpec = (k: string, v: string) => setFields((f) => ({ ...f, values: { ...f.values, [k]: v } }));

  const pickFile = async (file: File | undefined) => {
    if (!file) return;
    const err = validateFile(file, { types: DIAGRAM_TYPES });
    setFileError(err);
    if (err) return;
    const key = await upload.mutateAsync(file);
    setDiagram({ key, name: file.name });
  };

  const onSubmit = form.handleSubmit(async (v: Values) => {
    const body: Schemas["StockItemIn"] = {
      target_type: v.target_type, name: v.name, sku_code: v.sku_code || null, uom_primary: v.uom_primary, uom_alternate: v.uom_alternate || null,
      hsn_sac_code: v.hsn_sac_code || null, gst_rate: v.gst_rate || "0", valuation_method: v.valuation_method,
      opening_qty: v.opening_qty || "0", opening_rate: v.opening_rate || "0", custom_fields: writeFields(fields),
      ...(diagram ? { diagram_storage_key: diagram.key } : {}),
    };
    try {
      const out = await save.mutateAsync(body);
      router.push(p(`/items/${out.id}`));
    } catch (e) {
      applyServerErrors(form, e);
    }
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5">
      <PageHeader
        crumbs={[{ label: "Operations", href: p() }, { label: "Items", href: p("/items") }, { label: item ? "Edit" : "New" }]}
        title={item ? `Edit ${item.name}` : "New item or process"}
        description="Three short sections · you can change everything later"
        actions={<><Button onClick={() => router.back()}>Cancel</Button><Button type="submit" variant="primary" loading={save.isPending}><Save /> {item ? "Save item" : "Create item"}</Button></>}
      />
      <Card title="1 · Basics" description="Name, code and unit">
        <Segmented
          aria-label="Kind"
          value={type}
          onChange={(v) => form.setValue("target_type", v)}
          options={[{ value: "STOCK_ITEM", label: "Stock item" }, { value: "STANDALONE_PROCESS", label: "Standalone process" }]}
        />
        <p className="m-0 text-xs text-fg-muted">
          {type === "STOCK_ITEM" ? "For parts you make and sell — quantities stay in sync with Accounts." : "For maintenance, R&D or service jobs, counted in your own unit."}
        </p>
        <FieldRow>
          <Field label="Name" required error={errors.name?.message}><Input {...form.register("name")} placeholder="Component 1 · Flange 80NB" /></Field>
          <Field label="Code" error={errors.sku_code?.message}><Input {...form.register("sku_code")} placeholder="FG-C1-080" /></Field>
        </FieldRow>
        <FieldRow>
          <Field label="Unit" required error={errors.uom_primary?.message} hint={type === "STANDALONE_PROCESS" ? "e.g. Cycles, Batches, Jobs" : undefined}>
            <Input {...form.register("uom_primary")} />
          </Field>
          <Field label="Material"><Input value={spec("material_grade")} onChange={(e) => setSpec("material_grade", e.target.value)} placeholder="SS316" /></Field>
        </FieldRow>
      </Card>
      <Card title="2 · Drawing" description="Optional · PDF or image of the engineering drawing">
        <input ref={fileRef} type="file" accept={DIAGRAM_TYPES.join(",")} className="sr-only" onChange={(e) => void pickFile(e.target.files?.[0])} aria-label="Drawing file" />
        <button type="button" onClick={() => fileRef.current?.click()} className="flex flex-col items-center gap-1.5 rounded-xl border border-dashed border-line-strong bg-canvas px-4 py-6 text-[13px] text-fg-muted hover:bg-subtle">
          <FileUp className="size-5" aria-hidden />
          {upload.isPending ? "Uploading…" : diagram ? `Attached: ${diagram.name}` : item?.diagram_url ? "A drawing is attached · choose a file to replace it" : "Choose a drawing file"}
        </button>
        {fileError ? <p className="m-0 text-xs text-danger-text">{fileError}</p> : null}
        <Field label="Drawing revision"><Input value={spec("drawing_rev")} onChange={(e) => setSpec("drawing_rev", e.target.value)} placeholder="C" /></Field>
      </Card>
      <Card title="3 · Specs" description="Shown on run steps and in report tokens">
        <FieldRow>
          <Field label="Tolerance" hint="Free text, e.g. ±0.02 mm on bore"><Input value={spec("tolerance")} onChange={(e) => setSpec("tolerance", e.target.value)} /></Field>
          <Field label="Cycle time"><Input value={spec("cycle_time_min")} inputMode="decimal" suffix="min" onChange={(e) => setSpec("cycle_time_min", e.target.value)} /></Field>
        </FieldRow>
        <AdvancedSection title="Custom fields" description="Typed fields like hardness or machine ID">
          <CustomFieldsEditor value={fields} onChange={setFields} />
        </AdvancedSection>
      </Card>
      <AdvancedSection title="Tax and costing" description="Your accountant may set these">
        <div className="flex flex-col gap-3.5">
          <FieldRow>
            <Field label="Alternate unit"><Input {...form.register("uom_alternate")} /></Field>
            <Field label="HSN / SAC"><Input {...form.register("hsn_sac_code")} /></Field>
          </FieldRow>
          <FieldRow>
            <Field label="GST rate">
              <Controller control={form.control} name="gst_rate" render={({ field }) => <DecimalInput kind="qty" suffix="%" value={field.value} onValueChange={(v) => field.onChange(v ?? "0")} />} />
            </Field>
            <Field label="Valuation">
              <NativeSelect {...form.register("valuation_method")}>
                <option value="WEIGHTED_AVG">Weighted average</option>
                <option value="FIFO">FIFO</option>
                <option value="LIFO">LIFO</option>
                <option value="STANDARD">Standard cost</option>
              </NativeSelect>
            </Field>
          </FieldRow>
          {!item ? (
            <FieldRow>
              <Field label="Opening quantity">
                <Controller control={form.control} name="opening_qty" render={({ field }) => <DecimalInput kind="qty" decimals={4} value={field.value} onValueChange={(v) => field.onChange(v ?? "0")} />} />
              </Field>
              <Field label="Opening rate">
                <Controller control={form.control} name="opening_rate" render={({ field }) => <DecimalInput prefix="₹" value={field.value} onValueChange={(v) => field.onChange(v ?? "0")} />} />
              </Field>
            </FieldRow>
          ) : null}
        </div>
      </AdvancedSection>
    </form>
  );
}
