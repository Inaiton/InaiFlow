"use client";

import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import type { Schemas } from "@/core/api/types";
import { toIsoDate } from "@/core/dates";
import { Button, DatePicker, Dialog, DialogContent, Field, Hint, Input, Select, Textarea } from "@/components/ui";
import { useDecideJoinRequest, useInvite, useUpdateMember } from "../api";
import { useRoleOptions } from "./role-options";

/** Date-only expiry → end-of-day UTC timestamp for the API (`datetime`). */
export const expiryToTimestamp = (d: string | null): string | null => (d ? `${d}T23:59:59Z` : null);
export const timestampToDate = (t: string | null | undefined): string | null => (t ? t.slice(0, 10) : null);
const tomorrow = () => toIsoDate(new Date(Date.now() + 86_400_000));

export function InviteDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const invite = useInvite();
  const { options } = useRoleOptions();
  const [emails, setEmails] = useState("");
  const [roleId, setRoleId] = useState("");
  const [expiry, setExpiry] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const list = emails.split(/[,\s]+/).map((e) => e.trim().toLowerCase()).filter(Boolean);
  const valid = list.length > 0 && list.every((e) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e));
  const submit = async () => {
    setError(null);
    const failed: string[] = [];
    for (const email of list) {
      try {
        await invite.mutateAsync({ email, role_id: roleId, access_expires_at: expiryToTimestamp(expiry) });
      } catch (e) {
        failed.push(`${email}: ${describeError(e)}`);
      }
    }
    if (failed.length) setError(failed.join("\n"));
    else {
      setEmails("");
      onOpenChange(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Invite a member" description="They’ll get an email and see the invite in their personal space"
        footer={<><Button onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="primary" disabled={!valid || !roleId} loading={invite.isPending} onClick={() => void submit()}>Send {list.length > 1 ? `${list.length} invitations` : "invitation"}</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Field label="Email addresses" hint="Separate multiple emails with commas"><Textarea rows={2} value={emails} onChange={(e) => setEmails(e.target.value)} placeholder="karthik@company.in, devi@company.in" /></Field>
          <Field label="Role" required><Select value={roleId} onValueChange={setRoleId} options={options} placeholder="Choose a role" /></Field>
          <Field label="Access expires" hint="Pick a date for external CAs and auditors — leave empty for no expiry">
            <DatePicker value={expiry} onValueChange={setExpiry} min={tomorrow()} />
          </Field>
          <Hint tone="sky">Two-factor sign-in is required on first access for external collaborators when your security policy enforces it.</Hint>
          {error ? <Hint tone="danger"><span className="whitespace-pre-line">{error}</span></Hint> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function EditMemberDialog({ member, onClose }: { member: Schemas["MemberOut"]; onClose: () => void }) {
  const update = useUpdateMember();
  const { options } = useRoleOptions();
  const [roleId, setRoleId] = useState(member.role_id);
  const [expiry, setExpiry] = useState<string | null>(timestampToDate(member.access_expires_at));
  const submit = () =>
    update.mutate({ id: member.membership_id, body: { role_id: roleId, access_expires_at: expiryToTimestamp(expiry) } }, { onSuccess: onClose });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm" title={`Edit ${member.full_name}`} description={member.email}
        footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={update.isPending} onClick={submit}>Save</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Field label="Role"><Select value={roleId} onValueChange={setRoleId} options={options.some((o) => o.value === member.role_id) ? options : [{ value: member.role_id, label: member.role_name }, ...options]} /></Field>
          <Field label="Access expires" hint="Empty = never"><DatePicker value={expiry} onValueChange={setExpiry} min={tomorrow()} /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ApproveRequestDialog({ request, onClose }: { request: Schemas["JoinRequestOut"]; onClose: () => void }) {
  const decide = useDecideJoinRequest();
  const { options } = useRoleOptions();
  const [roleId, setRoleId] = useState("");
  const [expiry, setExpiry] = useState<string | null>(null);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm" title="Review join request" description={`${request.full_name} · ${request.email}`}
        footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!roleId} loading={decide.isPending}
          onClick={() => decide.mutate({ id: request.id, approve: { role_id: roleId, access_expires_at: expiryToTimestamp(expiry) } }, { onSuccess: onClose })}>Approve</Button></>}>
        <div className="flex flex-col gap-3.5">
          {request.message ? <Hint tone="gray" title="Message">“{request.message}”</Hint> : null}
          <Field label="Email"><Input readOnly value={`${request.email}${request.is_email_verified ? " · verified" : " · not verified"}`} /></Field>
          {request.professional_reg_no ? <Field label="Professional reg. no."><Input readOnly value={request.professional_reg_no} /></Field> : null}
          <Field label="Assign role" required><Select value={roleId} onValueChange={setRoleId} options={options} placeholder="Choose a role" /></Field>
          <Field label="Access expires" hint="Empty = never"><DatePicker value={expiry} onValueChange={setExpiry} min={tomorrow()} /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}
