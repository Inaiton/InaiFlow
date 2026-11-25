"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Field, Input, NativeSelect, Textarea } from "@/components/ui/input";
import { errorMessage } from "@/lib/api/errors";
import { useCreateConfig } from "./api";
import { CATEGORIES, type ConfigTab } from "./categories";

export function NewConfigDialog({ tab, onClose }: { tab: ConfigTab; onClose: () => void }) {
  const router = useRouter();
  const create = useCreateConfig();
  const options = Object.entries(CATEGORIES).filter(([, m]) => m.tab === tab || tab === "other");
  const [category, setCategory] = useState(options[0]?.[0] ?? "");
  const [custom, setCustom] = useState("");
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [effective, setEffective] = useState("");
  const [payload, setPayload] = useState("{}");
  let parsed: unknown = undefined;
  try {
    parsed = JSON.parse(payload);
  } catch {
    parsed = undefined;
  }
  const cat = (category === "__custom" ? custom : category).trim().toUpperCase();
  const valid = /^[A-Z0-9_]+$/.test(cat) && key.trim().length > 0 && name.trim().length > 0 && parsed !== undefined;

  return (
    <ConfirmReasonDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title="New configuration"
      confirmLabel="Create"
      pending={create.isPending}
      extraValid={valid}
      onConfirm={(reason) =>
        create.mutate(
          { config_category: cat, config_key: key.trim(), display_name: name.trim(), payload: parsed, effective_from: effective || null, reason },
          {
            onSuccess: (c) => {
              toast.success("Configuration created");
              router.push(`/config/${c.id}`);
            },
            onError: (e) => toast.error(errorMessage(e)),
          },
        )
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <Field label="Category">
          <NativeSelect value={category} onChange={(e) => setCategory(e.target.value)}>
            {options.map(([c, m]) => (
              <option key={c} value={c}>
                {m.label}
              </option>
            ))}
            <option value="__custom">Other…</option>
          </NativeSelect>
        </Field>
        {category === "__custom" ? (
          <Field label="Custom category" hint="UPPER_SNAKE_CASE">
            <Input value={custom} onChange={(e) => setCustom(e.target.value)} />
          </Field>
        ) : (
          <Field label="Effective from (optional)">
            <Input type="date" value={effective} onChange={(e) => setEffective(e.target.value)} />
          </Field>
        )}
        <Field label="Key">
          <Input value={key} onChange={(e) => setKey(e.target.value)} placeholder="default" className="font-mono" />
        </Field>
        <Field label="Display name">
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
      </div>
      <Field label="Initial payload (JSON)" error={parsed === undefined ? "Invalid JSON" : undefined} hint="Use the structured editor after creating.">
        <Textarea className="min-h-28 font-mono text-xs" value={payload} onChange={(e) => setPayload(e.target.value)} spellCheck={false} />
      </Field>
    </ConfirmReasonDialog>
  );
}
