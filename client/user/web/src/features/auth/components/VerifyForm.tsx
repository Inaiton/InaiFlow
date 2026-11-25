"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { describeError } from "@/core/api/error-messages";
import { useZodForm } from "@/core/forms";
import { Button } from "@/components/ui/button";
import { Hint } from "@/components/ui/feedback";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Stepper } from "@/components/ui/stepper";
import { AuthCard } from "@/components/shell/AuthShell";
import { useResendVerification, useVerifyEmail } from "../api";
import { verifySchema } from "../schemas";
import { CodeInput } from "./CodeInput";
import { ONBOARDING_STEPS } from "./SignupForm";

const COOLDOWN = 30;

function useCooldown(): [number, () => void] {
  const [left, setLeft] = useState(0);
  useEffect(() => {
    if (left <= 0) return;
    const t = setTimeout(() => setLeft((l) => l - 1), 1000);
    return () => clearTimeout(t);
  }, [left]);
  return [left, () => setLeft(COOLDOWN)];
}

export function VerifyForm() {
  const params = useSearchParams();
  const router = useRouter();
  const verify = useVerifyEmail();
  const resend = useResendVerification();
  const [left, startCooldown] = useCooldown();
  const [error, setError] = useState<string | null>(null);
  const form = useZodForm(verifySchema, { defaultValues: { email: params.get("email") ?? "", code: "" } });
  const { errors } = form.formState;

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await verify.mutateAsync(v);
      router.replace(`/login?verified=1&email=${encodeURIComponent(v.email)}&next=${encodeURIComponent("/me/organizations")}`);
    } catch (e) {
      setError(describeError(e));
    }
  });

  const onResend = async () => {
    const ok = await form.trigger("email");
    if (!ok) return;
    await resend.mutateAsync({ email: form.getValues("email") });
    startCooldown();
  };

  return (
    <div className="flex flex-col gap-5">
      <Stepper steps={ONBOARDING_STEPS} current={1} />
      <AuthCard title="Verify your email" description="We sent a 6-digit code. It’s valid for 10 minutes." footer={<Link href="/login">Back to sign in</Link>}>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <Field label="Email address" error={errors.email?.message}>
            <Input type="email" autoComplete="email" {...form.register("email")} />
          </Field>
          <Field label="Email code" error={errors.code?.message}>
            <CodeInput autoFocus {...form.register("code")} />
          </Field>
          {error ? <Hint tone="danger">{error}</Hint> : null}
          <Button type="submit" variant="primary" size="lg" loading={verify.isPending}>Verify &amp; continue</Button>
        </form>
        <Button variant="ghost" onClick={() => void onResend()} disabled={left > 0} loading={resend.isPending}>
          {left > 0 ? `Resend in 0:${String(left).padStart(2, "0")}` : "Resend code"}
        </Button>
      </AuthCard>
    </div>
  );
}
