"use client";

import { Combobox } from "@/components/ui";
import { useStates } from "@/features/me/api";

/** State picker backed by GET /meta/states (shown as "Tamil Nadu (33)"). */
export function StateSelect({ value, onChange, id, ...aria }: { value: string; onChange: (v: string) => void; id?: string; "aria-invalid"?: boolean; "aria-describedby"?: string }) {
  const states = useStates();
  return (
    <Combobox
      id={id}
      value={value}
      onValueChange={onChange}
      loading={states.isPending}
      placeholder="Select state"
      searchPlaceholder="Search states…"
      options={(states.data ?? []).map((s) => ({ value: s.code, label: `${s.name} (${s.code})` }))}
      {...aria}
    />
  );
}
