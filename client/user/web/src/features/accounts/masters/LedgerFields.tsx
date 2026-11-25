"use client";

import { Controller, type UseFormReturn } from "react-hook-form";
import { AdvancedSection, DecimalInput, Field, FieldRow, Input, NativeSelect, Section, SwitchRow, Textarea } from "@/components/ui";
import { GroupSelect, MSME_TYPES, StateSelect } from "../components/Selects";
import type { LedgerClass } from "../lib/group-tree";
import { partsFromGstin, type LedgerForm, type LedgerValues } from "./ledger-schema";

type Form = UseFormReturn<LedgerForm, unknown, LedgerValues>;

export function LedgerBasics({ form, compact }: { form: Form; compact?: boolean }) {
  const { register, control, formState: { errors } } = form;
  return (
    <div className="flex flex-col gap-3">
      <FieldRow>
        <Field label="Name" required error={errors.name?.message}><Input autoFocus {...register("name")} /></Field>
        {compact ? null : <Field label="Alias"><Input {...register("alias")} /></Field>}
      </FieldRow>
      <FieldRow>
        <Field label="Under group" required error={errors.group_id?.message}>
          <Controller control={control} name="group_id" render={({ field }) => <GroupSelect value={field.value} onValueChange={field.onChange} />} />
        </Field>
        <Field label="Opening balance" error={errors.opening_balance?.message}>
          <div className="flex gap-2">
            <Controller control={control} name="opening_balance" render={({ field }) => <DecimalInput value={field.value} onValueChange={(v) => field.onChange(v ?? "")} prefix="₹" />} />
            <NativeSelect className="w-20" aria-label="Dr or Cr" {...register("opening_balance_type")}><option value="DR">Dr</option><option value="CR">Cr</option></NativeSelect>
          </div>
        </Field>
      </FieldRow>
    </div>
  );
}

export function PartyFields({ form }: { form: Form }) {
  const { register, control, setValue, getValues, formState: { errors } } = form;
  const gstin = register("gstin");
  return (
    <div className="flex flex-col gap-3">
      <FieldRow>
        <Field label="GSTIN / UIN" error={errors.gstin?.message} hint="State and PAN fill in automatically">
          <Input {...gstin} onChange={(e) => {
            void gstin.onChange(e);
            const p = partsFromGstin(e.target.value);
            if (p) {
              setValue("state_code", p.state_code);
              if (!getValues("pan")) setValue("pan", p.pan);
            }
          }} className="uppercase" />
        </Field>
        <Field label="State (place of supply)">
          <Controller control={control} name="state_code" render={({ field }) => <StateSelect value={field.value} onValueChange={field.onChange} />} />
        </Field>
      </FieldRow>
      <FieldRow>
        <Field label="PAN" error={errors.pan?.message}><Input {...register("pan")} className="uppercase" /></Field>
        <Field label="MSME type" hint="Micro/Small suppliers get the 45-day payment flag">
          <NativeSelect {...register("msme_type")}>{MSME_TYPES.map((m) => <option key={m} value={m}>{m ? m.charAt(0) + m.slice(1).toLowerCase() : "Not registered"}</option>)}</NativeSelect>
        </Field>
      </FieldRow>
      <FieldRow>
        <Field label="Udyam no."><Input {...register("udyam_no")} /></Field>
        <Field label="Deductee type (TDS)">
          <NativeSelect {...register("deductee_type")}><option value="">—</option><option value="INDIVIDUAL">Individual / HUF</option><option value="COMPANY">Company / Firm</option></NativeSelect>
        </Field>
      </FieldRow>
      <Field label="Address"><Textarea rows={2} {...register("address")} /></Field>
      <FieldRow>
        <Field label="Email" error={errors.email?.message}><Input type="email" {...register("email")} /></Field>
        <Field label="Phone"><Input {...register("phone")} /></Field>
      </FieldRow>
      <div className="grid gap-2 md:grid-cols-2">
        <Controller control={control} name="is_sez" render={({ field }) => <SwitchRow label="SEZ party" description="Supplies taxed as IGST" checked={field.value} onCheckedChange={field.onChange} />} />
        <Controller control={control} name="is_unregistered" render={({ field }) => <SwitchRow label="Unregistered (B2C)" checked={field.value} onCheckedChange={field.onChange} />} />
      </div>
    </div>
  );
}

export function BankFields({ form }: { form: Form }) {
  const { register, formState: { errors } } = form;
  return (
    <FieldRow>
      <Field label="Account no."><Input {...register("bank_account")} /></Field>
      <Field label="IFSC" error={errors.ifsc?.message}><Input {...register("ifsc")} className="uppercase" /></Field>
    </FieldRow>
  );
}

export function CreditFields({ form }: { form: Form }) {
  const { register, control, formState: { errors } } = form;
  return (
    <div className="flex flex-col gap-3">
      <Controller control={control} name="maintain_bill_by_bill" render={({ field }) => <SwitchRow label="Maintain balances bill-by-bill" description="Required for ageing, outstanding and reminders" checked={field.value} onCheckedChange={field.onChange} />} />
      <FieldRow>
        <Field label="Default credit period (days)" error={errors.default_credit_days?.message}><Input inputMode="numeric" {...register("default_credit_days")} /></Field>
        <Field label="Credit limit" error={errors.credit_limit?.message}>
          <Controller control={control} name="credit_limit" render={({ field }) => <DecimalInput value={field.value} onValueChange={(v) => field.onChange(v ?? "")} prefix="₹" />} />
        </Field>
      </FieldRow>
    </div>
  );
}

export function TaxFields({ form }: { form: Form }) {
  const { register } = form;
  return (
    <div className="flex flex-col gap-3">
      <FieldRow>
        <Field label="Type of duty / tax"><NativeSelect {...register("tax_type")}><option value="">Others</option><option value="GST">GST</option><option value="TDS">TDS</option><option value="TCS">TCS</option></NativeSelect></Field>
        <Field label="GST head"><NativeSelect {...register("gst_head")}><option value="">—</option>{["CGST", "SGST", "UTGST", "IGST", "CESS", "RCM"].map((h) => <option key={h}>{h}</option>)}</NativeSelect></Field>
      </FieldRow>
      <FieldRow>
        <Field label="Rate %"><Input inputMode="decimal" {...register("tax_rate")} /></Field>
        <Field label="TDS section"><Input placeholder="e.g. 194C" {...register("tds_section")} /></Field>
      </FieldRow>
    </div>
  );
}

export function InterestFields({ form }: { form: Form }) {
  const { register } = form;
  return (
    <FieldRow>
      <Field label="Interest rate % p.a."><Input inputMode="decimal" {...register("interest_rate")} /></Field>
      <Field label="Applies to"><NativeSelect {...register("interest_basis")}><option value="PAST_DUE">Past due date</option><option value="ALL">All balances</option></NativeSelect></Field>
      <Field label="Grace days"><Input inputMode="numeric" {...register("grace_days")} /></Field>
    </FieldRow>
  );
}

/** All sections for the full ledger master screen. */
export function LedgerSections({ form, cls }: { form: Form; cls: LedgerClass }) {
  const { control } = form;
  return (
    <div className="flex flex-col gap-5">
      <Section title="Basic & group"><LedgerBasics form={form} /></Section>
      {cls === "party" ? <Section title="Bill-by-bill & credit control"><CreditFields form={form} /></Section> : null}
      {cls === "party" ? <Section title="Party profile & tax registration"><PartyFields form={form} /></Section> : null}
      {cls === "party" || cls === "bank" ? <Section title="Bank details"><BankFields form={form} /></Section> : null}
      {cls === "tax" ? <Section title="Statutory details"><TaxFields form={form} /></Section> : null}
      <AdvancedSection title="More options" description="Interest, bill-by-bill for non-party ledgers, status">
        <div className="flex flex-col gap-4">
          {cls !== "party" ? <CreditFields form={form} /> : null}
          <InterestFields form={form} />
          <Controller control={control} name="is_active" render={({ field }) => <SwitchRow label="Active" description="Inactive ledgers are hidden from voucher entry" checked={field.value} onCheckedChange={field.onChange} />} />
        </div>
      </AdvancedSection>
    </div>
  );
}
