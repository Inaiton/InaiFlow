"use client";

import { useState } from "react";
import { Button, Combobox, DatePicker, Dialog, DialogContent, Field, Hint, Input } from "@/components/ui";
import { useAuditorInvite } from "../../api/iso";
import { useOpsItems } from "../../api/items";
import { useRuns } from "../../api/runs";

function MultiPick({ options, value, onChange, placeholder, onSearch }: { options: { value: string; label: string; hint?: string }[]; value: string[]; onChange: (v: string[]) => void; placeholder: string; onSearch: (q: string) => void }) {
  const label = (id: string) => options.find((o) => o.value === id)?.label ?? id.slice(0, 8);
  return (
    <div className="flex flex-col gap-2">
      {value.length ? (
        <div className="flex flex-wrap gap-1.5">
          {value.map((id) => (
            <button key={id} type="button" onClick={() => onChange(value.filter((v) => v !== id))} className="rounded-md bg-subtle px-2 py-1 text-xs text-fg-2 hover:bg-line" aria-label={`Remove ${label(id)}`}>{label(id)} ×</button>
          ))}
        </div>
      ) : null}
      <Combobox value={null} onValueChange={(v) => !value.includes(v) && onChange([...value, v])} options={options} placeholder={placeholder} onSearch={onSearch} />
    </div>
  );
}

/** Time-bound read-only guest access for an external ISO auditor, scoped to items / runs (design Ops-ISO-Guest). */
export function AuditorInviteDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const invite = useAuditorInvite();
  const [email, setEmail] = useState("");
  const [expires, setExpires] = useState<string | null>(null);
  const [itemIds, setItemIds] = useState<string[]>([]);
  const [runIds, setRunIds] = useState<string[]>([]);
  const [iq, setIq] = useState("");
  const [rq, setRq] = useState("");
  const items = useOpsItems({ q: iq || undefined, limit: 30, offset: 0 });
  const runs = useRuns({ q: rq || undefined, limit: 30, offset: 0 });
  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const submit = async () => {
    await invite.mutateAsync({ email: email.trim(), access_expires_at: `${expires}T23:59:59Z`, stock_item_ids: itemIds, period_run_ids: runIds });
    setEmail(""); setItemIds([]); setRunIds([]);
    onOpenChange(false);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Invite an external ISO auditor" description="Read-only access to quality records — never payroll or margins."
        footer={<><Button onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="primary" disabled={!validEmail || !expires} loading={invite.isPending} onClick={() => void submit()}>Send invite</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Field label="Auditor email" required><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="auditor@certbody.com" /></Field>
          <Field label="Access ends on" required hint="Access stops automatically at the end of this day"><DatePicker value={expires} onValueChange={setExpires} /></Field>
          <Field label="Limit to items" hint="Leave empty to allow all items">
            <MultiPick value={itemIds} onChange={setItemIds} onSearch={setIq} placeholder="Add an item" options={(items.data?.items ?? []).map((i) => ({ value: i.id, label: i.name }))} />
          </Field>
          <Field label="Limit to runs" hint="Leave empty to allow all runs">
            <MultiPick value={runIds} onChange={setRunIds} onSearch={setRq} placeholder="Add a run" options={(runs.data?.items ?? []).map((r) => ({ value: r.id, label: r.run_title }))} />
          </Field>
          <Hint tone="sky">The auditor must use two-factor sign-in. You can revoke access any time from Members.</Hint>
        </div>
      </DialogContent>
    </Dialog>
  );
}
