"use client";

import { Controller } from "react-hook-form";
import { z } from "zod";
import type { Schemas } from "@/core/api/types";
import { formatDate } from "@/core/dates";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { useCan } from "@/core/permissions/Can";
import { AdvancedSection, Button, Card, Field, FieldRow, Input, Select } from "@/components/ui";
import { GST_REG_TYPES, GSTIN_RE, INDUSTRIES, PAN_RE, TAN_RE } from "@/features/org-create/schema";
import { StateSelect } from "@/features/org-create/components/StateSelect";
import { useUpdateOrgProfile } from "../api";

const optRe = (re: RegExp, msg: string) => z.string().trim().toUpperCase().refine((v) => v === "" || re.test(v), msg);
const schema = z.object({
  legal_name: z.string().trim().min(2).max(200),
  mailing_name: z.string().trim().max(200),
  address_line1: z.string().trim().min(3).max(200),
  address_line2: z.string().trim().max(200),
  city: z.string().trim().min(2).max(80),
  state_code: z.string().min(1),
  pincode: z.string().trim().regex(/^\d{6}$/, "6-digit PIN code"),
  contact_email: z.email().trim(),
  contact_phone: z.string().trim().min(7).max(20),
  gst_reg_type: z.string().min(1),
  gstin: optRe(GSTIN_RE, "Invalid GSTIN"),
  pan: optRe(PAN_RE, "Invalid PAN"),
  tan: optRe(TAN_RE, "Invalid TAN"),
  cin_or_udyam: z.string().trim().max(30),
  epf_code: z.string().trim().max(30),
  esic_code: z.string().trim().max(30),
  industry_type: z.string().min(1),
  iso_standard: z.string().trim().max(40),
});

const n = (s: string) => (s === "" ? null : s);

export function OrgProfileForm({ org }: { org: Schemas["OrgOut"] }) {
  const canEdit = useCan("organization.profile", "FULL");
  const update = useUpdateOrgProfile();
  const form = useZodForm(schema, {
    values: {
      legal_name: org.legal_name, mailing_name: org.mailing_name ?? "", address_line1: org.address_line1, address_line2: org.address_line2 ?? "",
      city: org.city, state_code: org.state_code, pincode: org.pincode, contact_email: org.contact_email, contact_phone: org.contact_phone,
      gst_reg_type: org.gst_reg_type, gstin: org.gstin ?? "", pan: org.pan ?? "", tan: org.tan ?? "", cin_or_udyam: org.cin_or_udyam ?? "",
      epf_code: org.epf_code ?? "", esic_code: org.esic_code ?? "", industry_type: org.industry_type, iso_standard: org.iso_standard ?? "",
    },
  });
  const { errors, isDirty } = form.formState;
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await update.mutateAsync({
        ...v, mailing_name: n(v.mailing_name), address_line2: n(v.address_line2), gstin: n(v.gstin), pan: n(v.pan), tan: n(v.tan),
        cin_or_udyam: n(v.cin_or_udyam), epf_code: n(v.epf_code), esic_code: n(v.esic_code), iso_standard: n(v.iso_standard),
      });
    } catch (e) {
      applyServerErrors(form, e);
    }
  });
  const ro = !canEdit;
  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <Card title="Essentials" description="Statutory identity used across invoices, returns and reports"
        actions={canEdit ? <><Button disabled={!isDirty} onClick={() => form.reset()}>Discard</Button><Button type="submit" variant="primary" disabled={!isDirty} loading={update.isPending}>Save changes</Button></> : null}>
        <fieldset disabled={ro} className="flex flex-col gap-4">
          <FieldRow>
            <Field label="Company legal name" error={errors.legal_name?.message} required><Input {...form.register("legal_name")} /></Field>
            <Field label="Mailing / trade name"><Input {...form.register("mailing_name")} /></Field>
            <Field label="Workspace code" hint="Share to receive join requests"><Input value={org.public_join_code} readOnly /></Field>
            <Field label="Workspace slug"><Input value={`/o/${org.workspace_slug}`} readOnly /></Field>
          </FieldRow>
          <Field label="Registered address" error={errors.address_line1?.message} required><Input {...form.register("address_line1")} /></Field>
          <Field label="Address line 2"><Input {...form.register("address_line2")} /></Field>
          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
            <Field label="City" error={errors.city?.message}><Input {...form.register("city")} /></Field>
            <Field label="State" error={errors.state_code?.message}>
              <Controller control={form.control} name="state_code" render={({ field }) => <StateSelect value={field.value} onChange={field.onChange} />} />
            </Field>
            <Field label="PIN code" error={errors.pincode?.message}><Input {...form.register("pincode")} /></Field>
          </div>
          <FieldRow>
            <Field label="Contact email" error={errors.contact_email?.message}><Input type="email" {...form.register("contact_email")} /></Field>
            <Field label="Contact phone" error={errors.contact_phone?.message}><Input type="tel" {...form.register("contact_phone")} /></Field>
            <Field label="Financial year begins" hint="Change via Accounts → Utilities"><Input value={formatDate(org.fy_begins_from)} readOnly /></Field>
            <Field label="Books beginning from"><Input value={formatDate(org.books_beginning_from)} readOnly /></Field>
            <Field label="Industry">
              <Controller control={form.control} name="industry_type" render={({ field }) => <Select value={field.value} onValueChange={field.onChange} options={INDUSTRIES} disabled={ro} />} />
            </Field>
            <Field label="ISO standard"><Input {...form.register("iso_standard")} /></Field>
          </FieldRow>
        </fieldset>
      </Card>
      <Card title="Tax registration">
        <fieldset disabled={ro} className="flex flex-col gap-4">
          <FieldRow>
            <Field label="GST registration">
              <Controller control={form.control} name="gst_reg_type" render={({ field }) => <Select value={field.value} onValueChange={field.onChange} options={GST_REG_TYPES} disabled={ro} />} />
            </Field>
            <Field label="GSTIN / UIN" error={errors.gstin?.message}><Input {...form.register("gstin")} /></Field>
            <Field label="PAN" error={errors.pan?.message}><Input {...form.register("pan")} /></Field>
            <Field label="CIN / Udyam (MSME)"><Input {...form.register("cin_or_udyam")} /></Field>
          </FieldRow>
          <AdvancedSection title="TAN, EPF & ESIC">
            <FieldRow>
              <Field label="TAN" error={errors.tan?.message}><Input {...form.register("tan")} /></Field>
              <Field label="EPF code"><Input {...form.register("epf_code")} /></Field>
              <Field label="ESIC code"><Input {...form.register("esic_code")} /></Field>
            </FieldRow>
          </AdvancedSection>
        </fieldset>
      </Card>
    </form>
  );
}
