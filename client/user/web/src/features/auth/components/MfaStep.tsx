"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import { useAuth } from "@/core/auth/AuthProvider";
import { useZodForm } from "@/core/forms";
import { Button } from "@/components/ui/button";
import { Hint } from "@/components/ui/feedback";
import { Field } from "@/components/ui/field";
import { AuthCard } from "@/components/shell/AuthShell";
import { useMfaVerify } from "../api";
import { mfaSchema } from "../schemas";
import { CodeInput } from "./CodeInput";

/** Second step of sign-in when the account has TOTP enabled (design: Auth-2FA.dc.html). */
export function MfaStep({ mfaToken, email, next, onBack }: { mfaToken: string; email: string; next: string; onBack: () => void }) {
  const router = useRouter();
  const { completeLogin } = useAuth();
  const verify = useMfaVerify();
  const [backup, setBackup] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useZodForm(mfaSchema, { defaultValues: { code: "" } });

  const onSubmit = form.handleSubmit(async ({ code }) => {
    setError(null);
    try {
      const res = await verify.mutateAsync({ mfa_token: mfaToken, code: code.replace(/\s/g, "") });
      completeLogin(res.token, res.user);
      router.replace(next);
    } catch (e) {
      setError(describeError(e));
      form.setValue("code", "");
    }
  });

  return (
    <AuthCard title="Two-factor authentication" description={backup ? "Enter one of your saved backup codes." : "Enter the 6-digit code from your authenticator app."}>
      <p className="text-[13px] text-fg-muted">Signing in as <strong className="text-fg">{email}</strong></p>
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <Field label={backup ? "Backup code" : "Authentication code"} error={form.formState.errors.code?.message}>
          <CodeInput autoFocus digitsOnly={!backup} {...form.register("code")} />
        </Field>
        {error ? <Hint tone="danger">{error}</Hint> : null}
        <Button type="submit" variant="primary" size="lg" loading={verify.isPending}>Verify</Button>
      </form>
      <div className="flex justify-between text-[13px]">
        <button type="button" className="font-medium text-link" onClick={() => { setBackup((b) => !b); form.reset({ code: "" }); }}>
          {backup ? "Use authenticator code" : "Use a backup code"}
        </button>
        <button type="button" className="text-fg-muted hover:text-fg" onClick={onBack}>Back to sign in</button>
      </div>
      <Hint tone="gray">External CAs and auditors must use 2FA for every organization that enforces it.</Hint>
    </AuthCard>
  );
}
