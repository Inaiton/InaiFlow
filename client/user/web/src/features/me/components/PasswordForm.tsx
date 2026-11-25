"use client";

import { useState } from "react";
import { z } from "zod";
import { describeError } from "@/core/api/error-messages";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { Button, Card, Field, Hint } from "@/components/ui";
import { PasswordInput } from "@/features/auth/components/PasswordInput";
import { passwordField } from "@/features/auth/schemas";
import { useChangePassword } from "../api";

const schema = z
  .object({ current_password: z.string().min(1, "Enter your current password"), new_password: passwordField, confirm: z.string() })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "Passwords don’t match" });

export function PasswordForm() {
  const change = useChangePassword();
  const [error, setError] = useState<string | null>(null);
  const form = useZodForm(schema, { defaultValues: { current_password: "", new_password: "", confirm: "" } });
  const { errors } = form.formState;
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await change.mutateAsync({ current_password: v.current_password, new_password: v.new_password });
      form.reset();
    } catch (e) {
      if (!applyServerErrors(form, e)) setError(describeError(e));
    }
  });
  return (
    <Card title="Password" description="Changing it signs you out on other devices">
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <Field label="Current password" error={errors.current_password?.message}><PasswordInput autoComplete="current-password" {...form.register("current_password")} /></Field>
        <Field label="New password" hint="10+ characters" error={errors.new_password?.message}><PasswordInput autoComplete="new-password" {...form.register("new_password")} /></Field>
        <Field label="Confirm new password" error={errors.confirm?.message}><PasswordInput autoComplete="new-password" {...form.register("confirm")} /></Field>
        {error ? <Hint tone="danger">{error}</Hint> : null}
        <div className="flex justify-end"><Button type="submit" loading={change.isPending}>Update password</Button></div>
      </form>
    </Card>
  );
}
