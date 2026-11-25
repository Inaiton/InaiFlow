"use client";

import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import type { Schemas } from "@/core/api/types";
import { formatMoney } from "@/core/money";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import { Button, Card, DecimalInput, ErrorState, Field, Hint, PageHeader, Select, Skeleton, SwitchRow } from "@/components/ui";
import { useSaveSecurity, useSecuritySettings } from "../api-rbac";

const TIMEOUTS = [30, 60, 240, 480, 720, 1440].map((m) => ({ value: String(m), label: m < 60 ? `${m} minutes` : `${m / 60} hour${m === 60 ? "" : "s"}` }));

function SecurityForm({ initial, canEdit }: { initial: Schemas["SecuritySettings"]; canEdit: boolean }) {
  const save = useSaveSecurity();
  const [s, setS] = useState(initial);
  const dirty = JSON.stringify(s) !== JSON.stringify(initial);
  const set = <K extends keyof typeof s>(k: K, v: (typeof s)[K]) => setS((p) => ({ ...p, [k]: v }));
  const timeouts = TIMEOUTS.some((t) => t.value === String(s.session_timeout_mins)) ? TIMEOUTS : [...TIMEOUTS, { value: String(s.session_timeout_mins), label: `${s.session_timeout_mins} minutes` }];
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card title="Security policies" description="Who must sign in how"
        actions={canEdit ? <Button variant="primary" disabled={!dirty} loading={save.isPending} onClick={() => save.mutate(s)}>Save</Button> : null}>
        <div className="flex flex-col">
          <SwitchRow label="Require 2FA for external collaborators" description="External CAs, consultants and auditors" checked={s.enforce_2fa_external} disabled={!canEdit} onCheckedChange={(v) => set("enforce_2fa_external", v)} />
          <SwitchRow label="Require 2FA for everyone" description="All internal members too" checked={s.enforce_2fa_all} disabled={!canEdit} onCheckedChange={(v) => set("enforce_2fa_all", v)} />
        </div>
        <Field label="Session timeout" hint="Idle sessions are signed out after this">
          <Select value={String(s.session_timeout_mins)} onValueChange={(v) => set("session_timeout_mins", Number(v))} options={timeouts} disabled={!canEdit} />
        </Field>
        {s.enforce_2fa_all ? <Hint tone="warning">Members without 2FA will be blocked from this organization until they turn it on.</Hint> : null}
      </Card>
      <Card title="Approval workflows" description="Who must approve what">
        <Field label="Voucher approval threshold" hint={s.voucher_approval_threshold ? `Vouchers above ${formatMoney(s.voucher_approval_threshold)} need approval` : "Empty = no approval required"}>
          <DecimalInput value={s.voucher_approval_threshold} onValueChange={(v) => set("voucher_approval_threshold", v)} prefix="₹" disabled={!canEdit} placeholder="No threshold" />
        </Field>
        <SwitchRow label="Require a reviewer for ISO documents" description="Draft → Under review → Approved, reviewer ≠ preparer" checked={s.require_reviewer_for_iso_docs} disabled={!canEdit}
          onCheckedChange={(v) => set("require_reviewer_for_iso_docs", v)} />
      </Card>
    </div>
  );
}

/** /o/[slug]/organization/security (design: Org-Security.dc.html). */
export function SecurityPage() {
  const { slug } = useOrg();
  const settings = useSecuritySettings();
  const canEdit = useCan("organization.security_policies", "FULL");
  return (
    <>
      <PageHeader crumbs={[{ label: "Organization", href: `/o/${slug}/organization/profile` }, { label: "Security" }]} title="Governance & security" description="Who must sign in how, and who must approve what" />
      {settings.isPending ? <Skeleton className="h-72" /> : settings.isError ? <ErrorState message={describeError(settings.error)} onRetry={() => void settings.refetch()} /> : (
        <SecurityForm key={settings.dataUpdatedAt} initial={settings.data} canEdit={canEdit} />
      )}
    </>
  );
}
