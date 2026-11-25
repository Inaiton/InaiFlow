"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { Button } from "@/components/ui/button";
import { Hint } from "@/components/ui/feedback";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { AuthCard } from "@/components/shell/AuthShell";
import { useForgotPassword, useResetPassword } from "../api";
import { forgotSchema, resetSchema } from "../schemas";
import { CodeInput } from "./CodeInput";
import { PasswordInput } from "./PasswordInput";

export function ForgotForm() {
  const router = useRouter();
  const forgot = useForgotPassword();
  const [sent, setSent] = useState(false);
  const form = useZodForm(forgotSchema, { defaultValues: { email: "" } });
  const onSubmit = form.handleSubmit(async (v) => {
    await forgot.mutateAsync(v);
    setSent(true);
  });
  return (
    <AuthCard title="Reset your password" description="We’ll email you a 6-digit code that is valid for 10 minutes." footer={<Link href="/login">Back to sign in</Link>}>
      {sent ? (
        <div className="flex flex-col gap-4">
          <Hint tone="success" title="Code sent">If an account exists for {form.getValues("email")}, a reset code is on its way.</Hint>
          <Button variant="primary" size="lg" onClick={() => router.push(`/reset?email=${encodeURIComponent(form.getValues("email"))}`)}>Enter code</Button>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <Field label="Email address" error={form.formState.errors.email?.message}>
            <Input type="email" autoComplete="email" autoFocus {...form.register("email")} />
          </Field>
          <Button type="submit" variant="primary" size="lg" loading={forgot.isPending}>Send reset code</Button>
        </form>
      )}
    </AuthCard>
  );
}

export function ResetForm() {
  const params = useSearchParams();
  const router = useRouter();
  const reset = useResetPassword();
  const [error, setError] = useState<string | null>(null);
  const form = useZodForm(resetSchema, { defaultValues: { email: params.get("email") ?? "", code: "", new_password: "", confirm: "" } });
  const { errors } = form.formState;
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await reset.mutateAsync({ email: v.email, code: v.code, new_password: v.new_password });
      router.replace(`/login?reset=1&email=${encodeURIComponent(v.email)}`);
    } catch (e) {
      if (!applyServerErrors(form, e)) setError(describeError(e));
    }
  });
  return (
    <AuthCard title="Choose a new password" description="Enter the code from your email and a new password." footer={<Link href="/forgot">Didn’t get a code?</Link>}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <Field label="Email address" error={errors.email?.message}>
          <Input type="email" autoComplete="email" {...form.register("email")} />
        </Field>
        <Field label="Reset code" error={errors.code?.message}>
          <CodeInput {...form.register("code")} />
        </Field>
        <Field label="New password" hint="10+ characters" error={errors.new_password?.message}>
          <PasswordInput autoComplete="new-password" {...form.register("new_password")} />
        </Field>
        <Field label="Confirm password" error={errors.confirm?.message}>
          <PasswordInput autoComplete="new-password" {...form.register("confirm")} />
        </Field>
        {error ? <Hint tone="danger">{error}</Hint> : null}
        <Button type="submit" variant="primary" size="lg" loading={reset.isPending}>Update password</Button>
      </form>
    </AuthCard>
  );
}
