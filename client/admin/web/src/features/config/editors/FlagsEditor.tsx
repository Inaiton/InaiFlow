"use client";

import { Switch } from "@/components/ui/switch";
import { JsonEditor } from "./JsonEditor";
import type { EditorProps } from "./types";

const isFlagMap = (v: unknown): v is Record<string, boolean> =>
  typeof v === "object" && v !== null && !Array.isArray(v) && Object.values(v).every((x) => typeof x === "boolean");

export function FlagsEditor(props: EditorProps) {
  if (!isFlagMap(props.value)) return <JsonEditor {...props} notice="Payload is not a flat map of booleans; editing as JSON." />;
  const flags = props.value;
  return (
    <ul className="divide-y divide-line rounded-md border border-line">
      {Object.entries(flags).map(([k, on]) => (
        <li key={k} className="flex items-center justify-between px-3 py-2.5">
          <span className="font-mono text-[13px] text-ink-2">{k}</span>
          <Switch checked={on} disabled={props.readOnly} onCheckedChange={(c) => props.onChange({ ...flags, [k]: c })} aria-label={k} />
        </li>
      ))}
      {Object.keys(flags).length === 0 ? <li className="px-3 py-4 text-[13px] text-faint">No flags</li> : null}
    </ul>
  );
}
