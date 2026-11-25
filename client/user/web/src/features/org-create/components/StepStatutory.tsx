"use client";

import { Controller } from "react-hook-form";
import { AdvancedSection, Field, FieldRow, Hint, Input, Select } from "@/components/ui";
import { GST_REG_TYPES, panFromGstin } from "../schema";
import type { OrgForm } from "./types";

export function StepStatutory({ form }: { form: OrgForm }) {
  const { errors } = form.formState;
  const regType = form.watch("gst_reg_type");
  const gstinReg = form.register("gstin");
  return (
    <div className="flex flex-col gap-4">
      <FieldRow>
        <Field label="GST registration status" required>
          <Controller control={form.control} name="gst_reg_type" render={({ field }) => <Select value={field.value} onValueChange={field.onChange} options={GST_REG_TYPES} />} />
        </Field>
        <Field label="GSTIN / UIN" hint="State code must match the registered state" error={errors.gstin?.message} required={regType !== "UNREGISTERED"}>
          <Input
            autoCapitalize="characters"
            disabled={regType === "UNREGISTERED"}
            {...gstinReg}
            onChange={(e) => {
              void gstinReg.onChange(e);
              const pan = panFromGstin(e.target.value.toUpperCase());
              if (pan && !form.getValues("pan")) form.setValue("pan", pan, { shouldValidate: true });
            }}
          />
        </Field>
        <Field label="Company PAN" hint="Auto-filled from GSTIN" error={errors.pan?.message}><Input autoCapitalize="characters" {...form.register("pan")} /></Field>
        <Field label="CIN / Udyam MSME" hint="Optional"><Input {...form.register("cin_or_udyam")} /></Field>
      </FieldRow>
      <AdvancedSection title="TDS, EPF & ESIC registrations" description="Needed for TDS returns and payroll statutory files — add later if unsure">
        <FieldRow>
          <Field label="TAN" error={errors.tan?.message}><Input autoCapitalize="characters" {...form.register("tan")} /></Field>
          <Field label="EPF establishment code"><Input {...form.register("epf_code")} /></Field>
          <Field label="ESIC code"><Input {...form.register("esic_code")} /></Field>
        </FieldRow>
      </AdvancedSection>
      {regType === "COMPOSITION" ? <Hint tone="warning">Composition dealers can’t collect GST on invoices — sales vouchers will be bill-of-supply.</Hint> : null}
    </div>
  );
}
