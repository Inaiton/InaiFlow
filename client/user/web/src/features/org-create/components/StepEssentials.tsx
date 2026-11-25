"use client";

import { Controller } from "react-hook-form";
import { Field, FieldRow, Input } from "@/components/ui";
import { StateSelect } from "./StateSelect";
import type { OrgForm } from "./types";

export function StepEssentials({ form }: { form: OrgForm }) {
  const { errors } = form.formState;
  return (
    <div className="flex flex-col gap-4">
      <FieldRow>
        <Field label="Company legal name" error={errors.legal_name?.message} required><Input autoFocus {...form.register("legal_name")} /></Field>
        <Field label="Mailing / trade name" hint="Optional — shown on invoices"><Input {...form.register("mailing_name")} /></Field>
      </FieldRow>
      <Field label="Registered address" error={errors.address_line1?.message} required><Input placeholder="Plot, street, area" {...form.register("address_line1")} /></Field>
      <Field label="Address line 2"><Input {...form.register("address_line2")} /></Field>
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        <Field label="City" error={errors.city?.message} required><Input {...form.register("city")} /></Field>
        <Field label="State" hint="Decides CGST + SGST vs IGST" error={errors.state_code?.message} required>
          <Controller control={form.control} name="state_code" render={({ field }) => <StateSelect value={field.value} onChange={field.onChange} />} />
        </Field>
        <Field label="PIN code" error={errors.pincode?.message} required><Input inputMode="numeric" maxLength={6} {...form.register("pincode")} /></Field>
      </div>
      <FieldRow>
        <Field label="Country" hint="Locked"><Input value="India" readOnly /></Field>
        <Field label="Currency" hint="Indian grouping 12,34,567.00"><Input value="₹ INR" readOnly /></Field>
        <Field label="Contact email" error={errors.contact_email?.message} required><Input type="email" {...form.register("contact_email")} /></Field>
        <Field label="Contact phone" error={errors.contact_phone?.message} required><Input type="tel" {...form.register("contact_phone")} /></Field>
      </FieldRow>
    </div>
  );
}
