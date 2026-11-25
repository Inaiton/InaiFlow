"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import { ApiError } from "@/core/api/errors";
import { useAuth } from "@/core/auth/AuthProvider";
import { safeNext } from "@/core/auth/RequireAuth";
import { useZodForm } from "@/core/forms";
import { Button } from "@/components/ui/button";
import { Hint } from "@/components/ui/feedback";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { CheckboxRow } from "@/components/ui/switch";
import { AuthCard } from "@/components/shell/AuthShell";
import { useLogin } from "../api";
import { loginSchema } from "../schemas";
import { GoogleButton } from "./GoogleButton";
import { MfaStep } from "./MfaStep";
import { PasswordInput } from "./PasswordInput";

export function LoginForm() {
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const router = useRouter();
  const { completeLogin } = useAuth();
  const login = useLogin();
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = useZodForm(loginSchema, { defaultValues: { email: params.get("email") ?? "", password: "", remember: true } });
  const { errors } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const res = await login.mutateAsync(values);
      if (res.status === "MFA_REQUIRED" && res.mfa_token) setMfaToken(res.mfa_token);
      else {
        completeLogin(res.token, res.user);
        router.replace(next);
      }
    } catch (e) {
      if (e instanceof ApiError && e.code === "EMAIL_NOT_VERIFIED") router.push(`/verify?email=${encodeURIComponent(values.email)}`);
      else if (e instanceof ApiError && e.code === "MFA_REQUIRED" && typeof (e.details as { mfa_token?: unknown } | null)?.mfa_token === "string")
        setMfaToken((e.details as { mfa_token: string }).mfa_token);
      else setError(describeError(e));
    }
  });

  if (mfaToken) return <MfaStep mfaToken={mfaToken} email={form.getValues("email")} next={next} onBack={() => setMfaToken(null)} />;

  return (
    <AuthCard
      title="Sign in to InaiFlow"
      description="One login for every organization you work with."
      footer={<>New to InaiFlow? <Link href="/signup" className="font-semibold">Create an account</Link></>}
    >
      {params.get("expired") ? <Hint tone="warning">Your session ended. Sign in again to continue.</Hint> : null}
      {params.get("verified") ? <Hint tone="success">Email verified — you can sign in now.</Hint> : null}
      {params.get("reset") ? <Hint tone="success">Password updated. Sign in with your new password.</Hint> : null}
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <Field label="Email address" error={errors.email?.message}>
          <Input type="email" autoComplete="email" autoFocus {...form.register("email")} />
        </Field>
        <Field label="Password" error={errors.password?.message}>
          <PasswordInput autoComplete="current-password" {...form.register("password")} />
        </Field>
        <div className="flex items-center justify-between gap-3">
          <CheckboxRow label="Keep me signed in on this device" checked={form.watch("remember")} onCheckedChange={(v) => form.setValue("remember", v)} />
          <Link href="/forgot" className="text-[13px] font-medium whitespace-nowrap">Forgot password?</Link>
        </div>
        {error ? <Hint tone="danger">{error}</Hint> : null}
        <Button type="submit" variant="primary" size="lg" loading={login.isPending}>Sign in</Button>
      </form>
      <GoogleButton next={next} />
    </AuthCard>
  );
}
