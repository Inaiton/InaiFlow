"use client";

import { useDeferredValue, useState } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useOrgs } from "@/features/organizations/api";

/** Search-and-pick an organization. */
export function OrgPicker({ value, onChange }: { value: { id: string; name: string } | null; onChange: (v: { id: string; name: string } | null) => void }) {
  const [q, setQ] = useState("");
  const dq = useDeferredValue(q);
  const orgs = useOrgs({ q: dq, limit: 8, offset: 0 });
  if (value)
    return (
      <div className="flex h-9 items-center justify-between rounded-md border border-line px-3 text-[13px]">
        <span className="text-ink">{value.name}</span>
        <button type="button" className="text-xs text-primary hover:underline" onClick={() => onChange(null)}>
          Change
        </button>
      </div>
    );
  return (
    <div>
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search organization…" aria-label="Search organization" />
      <ul className="mt-1 max-h-40 overflow-y-auto rounded-md border border-line">
        {orgs.data?.items.map((o) => (
          <li key={o.id}>
            <button type="button" className={cn("block w-full px-3 py-1.5 text-left text-[13px] hover:bg-canvas")} onClick={() => onChange({ id: o.id, name: o.legal_name })}>
              {o.legal_name} <span className="font-mono text-[11px] text-faint">{o.public_join_code}</span>
            </button>
          </li>
        ))}
        {orgs.data?.items.length === 0 ? <li className="px-3 py-2 text-[13px] text-faint">No match</li> : null}
      </ul>
    </div>
  );
}
