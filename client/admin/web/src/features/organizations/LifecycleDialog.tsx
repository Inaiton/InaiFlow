"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Field, Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/api/errors";
import { useLifecycle } from "./api";
import type { LifecycleAction } from "./constants";

const COPY: Record<LifecycleAction, { title: string; desc: string; destructive: boolean }> = {
  ACTIVATE: { title: "Activate organization", desc: "Members regain access immediately.", destructive: false },
  SUSPEND: { title: "Suspend organization", desc: "All members are blocked (403 ORG_SUSPENDED) until reactivated. Data is retained.", destructive: true },
  ARCHIVE: { title: "Archive organization", desc: "The organization becomes read-only and hidden from members. This is intended to be permanent.", destructive: true },
  EXTEND_TRIAL: { title: "Extend trial", desc: "Adds days to the current trial end date.", destructive: false },
};

export function LifecycleDialog({ orgId, orgName, action, onClose }: { orgId: string; orgName: string; action: LifecycleAction | null; onClose: () => void }) {
  const m = useLifecycle(orgId);
  const [days, setDays] = useState("14");
  const [confirmName, setConfirmName] = useState("");
  if (!action) return null;
  const c = COPY[action];
  const daysNum = Number.parseInt(days, 10);
  const daysValid = action !== "EXTEND_TRIAL" || (Number.isInteger(daysNum) && daysNum >= 1 && daysNum <= 365);
  const nameValid = action !== "ARCHIVE" || confirmName.trim() === orgName;
  return (
    <ConfirmReasonDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={c.title}
      description={`${orgName} — ${c.desc}`}
      destructive={c.destructive}
      confirmLabel={c.title.split(" ")[0]}
      pending={m.isPending}
      extraValid={daysValid && nameValid}
      onConfirm={(reason) =>
        m.mutate(
          { action, reason, trial_days: action === "EXTEND_TRIAL" ? daysNum : null },
          {
            onSuccess: () => {
              toast.success(`${c.title}: done`);
              onClose();
            },
            onError: (e) => toast.error(errorMessage(e)),
          },
        )
      }
    >
      {action === "EXTEND_TRIAL" ? (
        <Field label="Days to add" hint="1–365">
          <Input type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} />
        </Field>
      ) : null}
      {action === "ARCHIVE" ? (
        <Field label={`Type the legal name to confirm`} hint={orgName}>
          <Input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} />
        </Field>
      ) : null}
    </ConfirmReasonDialog>
  );
}
