"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { errorMessage } from "@/lib/api/errors";
import { formatINR } from "@/lib/money";
import type { Schemas } from "@/lib/api/client";
import { usePlans } from "@/features/plans/api";
import { usePlanChange } from "./api";

const QUOTAS = [
  ["max_internal_seats", "Internal seats"],
  ["max_external_collaborators", "External collaborators"],
  ["max_storage_gb", "Storage (GB)"],
] as const;

function initialOverrides(o: unknown): Record<string, string> {
  const src = typeof o === "object" && o !== null ? (o as Record<string, unknown>) : {};
  return Object.fromEntries(QUOTAS.map(([k]) => [k, src[k] == null ? "" : String(src[k])]));
}

export function PlanDialog({ org, open, onClose }: { org: Schemas["AdminOrgDetail"]; open: boolean; onClose: () => void }) {
  const plans = usePlans();
  const m = usePlanChange(org.id);
  const [planId, setPlanId] = useState(org.plan_id ?? "");
  const [ov, setOv] = useState(() => initialOverrides(org.quota_overrides));
  const invalid = Object.values(ov).some((v) => v !== "" && !/^\d+$/.test(v));

  const submit = (reason: string) => {
    const base = typeof org.quota_overrides === "object" && org.quota_overrides ? (org.quota_overrides as Record<string, unknown>) : {};
    const quota_overrides: Record<string, unknown> = { ...base };
    for (const [k] of QUOTAS) {
      if (ov[k]) quota_overrides[k] = Number.parseInt(ov[k]!, 10);
      else delete quota_overrides[k];
    }
    m.mutate(
      { plan_id: planId, quota_overrides, reason },
      {
        onSuccess: () => {
          toast.success("Plan updated");
          onClose();
        },
        onError: (e) => toast.error(errorMessage(e)),
      },
    );
  };

  return (
    <ConfirmReasonDialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title="Change plan & quotas"
      description={org.legal_name}
      confirmLabel="Save plan"
      pending={m.isPending}
      extraValid={!!planId && !invalid}
      onConfirm={submit}
    >
      <Field label="Plan">
        <NativeSelect value={planId} onChange={(e) => setPlanId(e.target.value)}>
          <option value="">Select a plan…</option>
          {plans.data?.map((p) => (
            <option key={p.id} value={p.id} disabled={!p.is_active && p.id !== org.plan_id}>
              {p.name} · {formatINR(p.monthly_price_inr, { dp: 0 })}/mo{p.is_active ? "" : " (inactive)"}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <div>
        <p className="mb-2 text-[13px] font-medium text-muted">Quota overrides (blank = plan default)</p>
        <div className="grid grid-cols-3 gap-2">
          {QUOTAS.map(([k, label]) => (
            <Field key={k} label={label}>
              <Input inputMode="numeric" value={ov[k] ?? ""} onChange={(e) => setOv({ ...ov, [k]: e.target.value.trim() })} aria-invalid={ov[k] !== "" && !/^\d+$/.test(ov[k] ?? "")} />
            </Field>
          ))}
        </div>
      </div>
    </ConfirmReasonDialog>
  );
}
