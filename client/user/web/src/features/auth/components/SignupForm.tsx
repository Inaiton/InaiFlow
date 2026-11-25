"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { Button } from "@/components/ui/button";
import { Field, FieldRow } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Stepper } from "@/components/ui/stepper";
import { AuthCard } from "@/components/shell/AuthShell";
import { useSignup } from "../api";
import { signupSchema } from "../schemas";
import { GoogleButton } from "./GoogleButton";
import { PasswordInput } from "./PasswordInput";

export const ONBOARDING_STEPS = [{ title: "Your details" }, { title: "Verify email" }, { title: "Join or create" }];

export function SignupForm() {
  const router = useRouter();
  const signup = useSignup();
  const form = useZodForm(signupSchema, { defaultValues: { first_name: "", last_name: "", email: "", password: "", confirm: "" } });
  const { errors } = form.formState;
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const res = await signup.mutateAsync({ full_name: `${v.first_name} ${v.last_name}`.trim(), email: v.email, password: v.password });
      router.push(res.verification_required ? `/verify?email=${encodeURIComponent(res.email)}` : `/login?email=${encodeURIComponent(res.email)}`);
    } catch (e) {
      applyServerErrors(form, e);
    }
  });
  return (
    <div className="flex flex-col gap-5">
      <Stepper steps={ONBOARDING_STEPS} current={0} />
      <AuthCard
        title="Create your InaiFlow account"
        description="You don’t need a company yet — join or create one after signing up."
        footer={<>Already have an account? <Link href="/login" className="font-semibold">Sign in</Link></>}
      >
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <FieldRow>
            <Field label="First name" error={errors.first_name?.message} required>
              <Input autoComplete="given-name" autoFocus {...form.register("first_name")} />
            </Field>
            <Field label="Last name" error={errors.last_name?.message}>
              <Input autoComplete="family-name" {...form.register("last_name")} />
            </Field>
          </FieldRow>
          <Field label="Email address" error={errors.email?.message} required>
            <Input type="email" autoComplete="email" {...form.register("email")} />
          </Field>
          <Field label="Password" hint="10+ characters; avoid common passwords" error={errors.password?.message} required>
            <PasswordInput autoComplete="new-password" {...form.register("password")} />
          </Field>
          <Field label="Confirm password" error={errors.confirm?.message} required>
            <PasswordInput autoComplete="new-password" {...form.register("confirm")} />
          </Field>
          <Button type="submit" variant="primary" size="lg" loading={signup.isPending}>Continue</Button>
          <p className="text-center text-xs text-fg-muted">By continuing you agree to the Terms and Privacy Policy.</p>
        </form>
        <GoogleButton next="/me/organizations" />
      </AuthCard>
    </div>
  );
}
