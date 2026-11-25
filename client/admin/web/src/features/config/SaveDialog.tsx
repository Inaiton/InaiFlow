"use client";

import { useState } from "react";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Field, Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { JsonDiffView } from "@/components/ui/json-diff-view";
import { todayISO } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";

export function SaveDialog({
  config,
  draft,
  statutory,
  pending,
  onClose,
  onSave,
}: {
  config: Schemas["ConfigOut"];
  draft: unknown;
  statutory: boolean;
  pending: boolean;
  onClose: () => void;
  onSave: (b: Schemas["ConfigUpdateIn"]) => void;
}) {
  const [effective, setEffective] = useState(statutory ? (config.effective_from ?? todayISO()) : "");
  const [active, setActive] = useState(config.is_active);
  const [name, setName] = useState(config.display_name);
  return (
    <ConfirmReasonDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={`Publish v${config.version + 1}`}
      description={`${config.config_category} / ${config.config_key}`}
      confirmLabel="Publish changes"
      pending={pending}
      extraValid={name.trim().length > 0}
      onConfirm={(reason) => onSave({ payload: draft, reason, display_name: name.trim(), is_active: active, effective_from: effective || null })}
    >
      <Field label="Display name">
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={statutory ? "Effective from" : "Effective from (optional)"} hint={statutory ? "Vouchers dated before this keep the previous version." : undefined}>
          <Input type="date" value={effective} onChange={(e) => setEffective(e.target.value)} />
        </Field>
        <Field label="Active">
          <div className="flex h-9 items-center">
            <Switch checked={active} onCheckedChange={setActive} aria-label="Active" />
          </div>
        </Field>
      </div>
      <div>
        <p className="mb-1 text-[13px] font-medium text-muted">Changes</p>
        <div className="max-h-56 overflow-y-auto">
          <JsonDiffView before={config.payload} after={draft} />
        </div>
      </div>
    </ConfirmReasonDialog>
  );
}
