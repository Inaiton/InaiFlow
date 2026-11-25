"use client";

import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import { Button, Dialog, DialogContent, Field, Hint, Input, Select } from "@/components/ui";
import { PasswordInput } from "@/features/auth/components/PasswordInput";
import { useMembers, useTransferOwnership } from "../api";

/**
 * Transfer ownership (design: Org-Transfer). Only rendered for the current owner (`is_owner` is an
 * ownership fact from /org/context, not a role-code check) with FULL on organization.members.
 */
export function TransferOwnershipButton() {
  const { context } = useOrg();
  const canManage = useCan("organization.members", "FULL");
  const [open, setOpen] = useState(false);
  if (!context.is_owner || !canManage) return null;
  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>Transfer</Button>
      {open ? <TransferDialog open={open} onOpenChange={setOpen} /> : null}
    </>
  );
}

function TransferDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { context } = useOrg();
  const members = useMembers({ status: "ACTIVE" });
  const transfer = useTransferOwnership();
  const [membershipId, setMembershipId] = useState("");
  const [password, setPassword] = useState("");
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const candidates = (members.data ?? []).filter((m) => !m.is_owner && !m.is_external && m.status === "ACTIVE");
  const ready = membershipId && password && typed.trim() === context.workspace_slug;
  const submit = async () => {
    setError(null);
    try {
      await transfer.mutateAsync({ membership_id: membershipId, password });
      onOpenChange(false);
    } catch (e) {
      setError(describeError(e));
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm" title="Transfer organization ownership" description="Only one Org owner exists. You will lose owner rights."
        footer={<><Button onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="destructive-solid" disabled={!ready} loading={transfer.isPending} onClick={() => void submit()}>Transfer ownership</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Hint tone="warning">The new owner gets full control, including billing. This can only be undone by them.</Hint>
          <Field label="New owner" hint="Must be an internal member">
            <Select value={membershipId} onValueChange={setMembershipId} placeholder={members.isPending ? "Loading…" : "Choose a member"}
              options={candidates.map((m) => ({ value: m.membership_id, label: m.full_name, hint: `${m.role_name}${m.mfa_enabled ? "" : " · 2FA off"}` }))} />
          </Field>
          <Field label={<>Type <strong>{context.workspace_slug}</strong> to confirm</>}><Input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" /></Field>
          <Field label="Your password"><PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></Field>
          {error ? <Hint tone="danger">{error}</Hint> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
