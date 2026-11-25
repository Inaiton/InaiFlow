"use client";

import { useQuery } from "@tanstack/react-query";
import QRCode from "qrcode";
import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import type { Schemas } from "@/core/api/types";
import { Badge, Button, Card, Dialog, DialogContent, Field, Hint, Input, Skeleton } from "@/components/ui";
import { CodeInput } from "@/features/auth/components/CodeInput";
import { PasswordInput } from "@/features/auth/components/PasswordInput";
import { useMfaDisable, useMfaEnable, useMfaSetup, useRegenerateRecoveryCodes } from "../api";
import { RecoveryCodes } from "./RecoveryCodes";

/** QR is rendered client-side to a data URL — the secret never leaves the browser again. */
function QrImage({ uri }: { uri: string }) {
  const qr = useQuery({ queryKey: ["mfa-qr", uri], queryFn: () => QRCode.toDataURL(uri, { margin: 1, width: 192 }), gcTime: 0, staleTime: Infinity });
  if (!qr.data) return <Skeleton className="size-48" />;
  // eslint-disable-next-line @next/next/no-img-element -- local data URL
  return <img src={qr.data} alt="Scan this QR code with your authenticator app" className="size-48 rounded-lg border border-line" />;
}

function SetupFlow({ setup, onDone }: { setup: Schemas["MfaSetupOut"]; onDone: (codes: string[]) => void }) {
  const enable = useMfaEnable();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const grouped = setup.secret.replace(/(.{4})/g, "$1 ").trim();
  const submit = async () => {
    setError(null);
    try {
      const res = await enable.mutateAsync({ code });
      onDone(res.recovery_codes);
    } catch (e) {
      setError(describeError(e));
    }
  };
  return (
    <div className="flex flex-col gap-4 sm:flex-row">
      <QrImage uri={setup.otpauth_uri} />
      <div className="flex flex-1 flex-col gap-3">
        <p className="text-[13px] text-fg-3">Scan with Google Authenticator, Microsoft Authenticator or Authy, then enter the 6-digit code.</p>
        <p className="text-xs text-fg-muted">Setup key: <code className="font-mono text-fg">{grouped}</code></p>
        <Field label="Code from app"><CodeInput value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></Field>
        {error ? <Hint tone="danger">{error}</Hint> : null}
        <Button variant="primary" disabled={code.length !== 6} loading={enable.isPending} onClick={() => void submit()}>Enable 2FA</Button>
      </div>
    </div>
  );
}

function DisableDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const disable = useMfaDisable();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setError(null);
    try {
      await disable.mutateAsync({ password, code });
      onOpenChange(false);
    } catch (e) {
      setError(describeError(e));
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm" title="Turn off two-factor?" description="Organizations that enforce 2FA will block your access until you turn it back on."
        footer={<><Button onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="destructive-solid" disabled={!password || code.length < 6} loading={disable.isPending} onClick={() => void submit()}>Turn off 2FA</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Field label="Password"><PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></Field>
          <Field label="Authenticator code"><CodeInput value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></Field>
          {error ? <Hint tone="danger">{error}</Hint> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function MfaCard({ enabled }: { enabled: boolean }) {
  const setup = useMfaSetup();
  const regen = useRegenerateRecoveryCodes();
  const [codes, setCodes] = useState<string[] | null>(null);
  const [disableOpen, setDisableOpen] = useState(false);
  const [regenCode, setRegenCode] = useState("");
  return (
    <Card title="Two-factor authentication" description="Required by organizations that protect external access" actions={enabled ? <Badge tone="success" dot>Authenticator active</Badge> : <Badge tone="warning">Off</Badge>}>
      {codes ? (
        <>
          <RecoveryCodes codes={codes} />
          <div className="flex justify-end"><Button variant="primary" onClick={() => { setCodes(null); setup.reset(); }}>I’ve saved them</Button></div>
        </>
      ) : enabled ? (
        <div className="flex flex-col gap-3">
          <p className="text-[13px] text-fg-3">Sign-ins ask for a code from your authenticator app. Lost your codes? Generate a fresh set.</p>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Current code" className="w-40"><Input inputMode="numeric" maxLength={6} value={regenCode} onChange={(e) => setRegenCode(e.target.value.replace(/\D/g, ""))} /></Field>
            <Button disabled={regenCode.length !== 6} loading={regen.isPending} onClick={() => void regen.mutateAsync({ code: regenCode }).then((r) => { setCodes(r.recovery_codes); setRegenCode(""); })}>
              New backup codes
            </Button>
            <div className="flex-1" />
            <Button variant="destructive" onClick={() => setDisableOpen(true)}>Turn off</Button>
          </div>
          {regen.isError ? <Hint tone="danger">{describeError(regen.error)}</Hint> : null}
          <DisableDialog open={disableOpen} onOpenChange={setDisableOpen} />
        </div>
      ) : setup.data ? (
        <SetupFlow setup={setup.data} onDone={setCodes} />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-[13px] text-fg-3">Protect your account with a 6-digit code from an authenticator app.</p>
          <Button variant="primary" loading={setup.isPending} onClick={() => setup.mutate()}>Set up 2FA</Button>
        </div>
      )}
    </Card>
  );
}
