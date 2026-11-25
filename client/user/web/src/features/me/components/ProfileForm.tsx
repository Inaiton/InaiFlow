"use client";

import { z } from "zod";
import { useZodForm, applyServerErrors } from "@/core/forms";
import type { Schemas } from "@/core/api/types";
import { Badge, Button, Card, Field, FieldRow, Input } from "@/components/ui";
import { useUpdateMe } from "../api";

const schema = z.object({
  full_name: z.string().trim().min(1, "Enter your name").max(120),
  mobile: z.string().trim().max(20).regex(/^[+\d\s-]*$/, "Use digits, spaces, + or -"),
  professional_reg_no: z.string().trim().max(40),
});

export function ProfileForm({ me }: { me: Schemas["MeOut"] }) {
  const update = useUpdateMe();
  const form = useZodForm(schema, { values: { full_name: me.full_name, mobile: me.mobile ?? "", professional_reg_no: me.professional_reg_no ?? "" } });
  const { errors, isDirty } = form.formState;
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await update.mutateAsync({ full_name: v.full_name, mobile: v.mobile || null, professional_reg_no: v.professional_reg_no || null });
    } catch (e) {
      applyServerErrors(form, e);
    }
  });
  return (
    <Card title="Profile" description="How you appear to every organization you work with">
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FieldRow>
          <Field label="Full name" error={errors.full_name?.message} required><Input autoComplete="name" {...form.register("full_name")} /></Field>
          <Field label="Email" hint={me.is_email_verified ? undefined : "Not verified yet"}>
            <Input value={me.email} readOnly suffix={me.is_email_verified ? <Badge tone="success">Verified</Badge> : undefined} />
          </Field>
          <Field label="Mobile" error={errors.mobile?.message}><Input type="tel" autoComplete="tel" placeholder="+91 98430 12345" {...form.register("mobile")} /></Field>
          <Field label="Professional reg. no." hint="CA / CMA / auditor registration, if any" error={errors.professional_reg_no?.message}>
            <Input {...form.register("professional_reg_no")} />
          </Field>
        </FieldRow>
        <div className="flex justify-end">
          <Button type="submit" variant="primary" disabled={!isDirty} loading={update.isPending}>Save profile</Button>
        </div>
      </form>
    </Card>
  );
}
