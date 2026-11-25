"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/states";
import { errorMessage } from "@/lib/api/errors";
import type { Schemas } from "@/lib/api/client";
import { codeSchema, otpSecretFromUri, passwordChangeSchema } from "./schemas";
import { useAdminMfaVerify } from "./api";

export function MfaStep({ challenge, onDone, onRestart }: { challenge: Schemas["AdminLoginOut"]; onDone: (r: Schemas["AdminLoginSuccessOut"]) => void; onRestart: () => void }) {
  const verify = useAdminMfaVerify();
  const [code, setCode] = useState("");
  const [pw, setPw] = useState({ new_password: "", confirm: "" });
  const [qr, setQr] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const needsPassword = challenge.status === "PASSWORD_CHANGE_REQUIRED";
  const uri = challenge.otpauth_uri;

  useEffect(() => {
    if (!uri) return;
    QRCode.toDataURL(uri, { margin: 1, width: 192 }).then(setQr, () => setQr(null));
  }, [uri]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const c = codeSchema.safeParse(code.trim());
    if (!c.success) return setFormError(c.error.issues[0]?.message ?? "Invalid code");
    if (needsPassword) {
      const p = passwordChangeSchema.safeParse(pw);
      if (!p.success) return setFormError(p.error.issues[0]?.message ?? "Invalid password");
    }
    verify.mutate(
      { mfa_token: challenge.mfa_token, code: c.data, new_password: needsPassword ? pw.new_password : null },
      { onSuccess: onDone, onError: (err) => setFormError(errorMessage(err)) },
    );
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      {uri ? (
        <div className="rounded-md border border-line bg-canvas p-3">
          <p className="text-[13px] font-medium text-ink-2">Set up your authenticator</p>
          <p className="mt-0.5 text-xs text-muted">MFA is mandatory for platform admins. Scan this code with an authenticator app.</p>
          <div className="mt-3 flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {qr ? <img src={qr} alt="TOTP QR code" width={144} height={144} className="rounded-md border border-line bg-white" /> : <Spinner />}
            <div className="min-w-0 text-xs text-muted">
              Can&apos;t scan? Enter this key:
              <code className="mt-1 block break-all rounded-sm bg-white px-1.5 py-1 font-mono text-[11px] text-ink-2">{otpSecretFromUri(uri) ?? "—"}</code>
            </div>
          </div>
        </div>
      ) : null}
      {needsPassword ? (
        <>
          <p className="rounded-md bg-warning-tint px-3 py-2 text-[13px] text-warning-ink">You must set a new password before continuing.</p>
          <Field label="New password" hint="10–128 characters, not your email.">
            <Input type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
          </Field>
          <Field label="Confirm new password">
            <Input type="password" autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
          </Field>
        </>
      ) : null}
      <Field label="Authenticator code (TOTP)">
        <Input
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          autoFocus
          className="font-mono tracking-[0.3em]"
        />
      </Field>
      {formError ? (
        <p role="alert" className="text-[13px] text-danger-ink">
          {formError}
        </p>
      ) : null}
      <Button type="submit" variant="primary" className="w-full" disabled={verify.isPending}>
        {verify.isPending ? <Spinner /> : null} Verify and sign in
      </Button>
      <button type="button" onClick={onRestart} className="w-full text-center text-xs text-faint hover:text-ink-2">
        Start over
      </button>
    </form>
  );
}
