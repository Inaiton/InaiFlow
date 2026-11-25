"use client";

import { useState } from "react";
import { z } from "zod";
import { describeError } from "@/core/api/error-messages";
import { formatDateTime } from "@/core/dates";
import { useZodForm } from "@/core/forms";
import { Button, Card, Field, Hint, Input, StatusBadge, Textarea } from "@/components/ui";
import { useCancelJoinRequest, useCreateJoinRequest, useMyJoinRequests } from "../api";

const schema = z.object({
  join_code: z.string().trim().toUpperCase().regex(/^ORG-[A-Z0-9]{4,8}$/, "Codes look like ORG-8492"),
  message: z.string().trim().max(500),
});

/** Pull join: request access with a workspace code; list and cancel own requests. */
export function JoinRequests() {
  const create = useCreateJoinRequest();
  const cancel = useCancelJoinRequest();
  const requests = useMyJoinRequests();
  const [sent, setSent] = useState<string | null>(null);
  const form = useZodForm(schema, { defaultValues: { join_code: "", message: "" } });
  const onSubmit = form.handleSubmit(async (v) => {
    setSent(null);
    try {
      const r = await create.mutateAsync({ join_code: v.join_code, message: v.message || null });
      setSent(r.org_name);
      form.reset();
    } catch (e) {
      form.setError("join_code", { message: describeError(e) });
    }
  });
  const pending = (requests.data ?? []).filter((r) => r.status === "PENDING");
  const past = (requests.data ?? []).filter((r) => r.status !== "PENDING").slice(0, 5);
  return (
    <Card title="Join with a code" description="Ask your admin for the workspace code, e.g. ORG-8492">
      <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
        <Field label="Workspace code" error={form.formState.errors.join_code?.message}>
          <Input placeholder="ORG-XXXX" autoCapitalize="characters" {...form.register("join_code")} />
        </Field>
        <Field label="Message (optional)" hint="Tell the admin who you are">
          <Textarea rows={2} {...form.register("message")} />
        </Field>
        <div className="flex justify-end"><Button type="submit" loading={create.isPending}>Request to join</Button></div>
      </form>
      {sent ? <Hint tone="success" title={`Request sent to ${sent}`}>An admin will review your verified profile and assign your role.</Hint> : null}
      {pending.length + past.length > 0 ? (
        <ul className="flex flex-col gap-2 border-t border-line pt-3">
          {[...pending, ...past].map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-3 text-[13px]">
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="font-semibold text-fg">{r.org_name}</span>
                <span className="text-xs text-fg-muted">{r.public_join_code} · {formatDateTime(r.created_at)}</span>
              </span>
              <StatusBadge status={r.status} />
              {r.status === "PENDING" ? (
                <Button size="sm" variant="ghost" loading={cancel.isPending && cancel.variables === r.id} onClick={() => cancel.mutate(r.id)}>Cancel</Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
