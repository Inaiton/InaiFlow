"use client";

import { Input } from "@/components/ui";
import { cn } from "@/lib/utils";
import { evaluateReading, toleranceHint, type QcField } from "../../lib/tolerance";

/** QC readings with nominal & tolerance hints; values coloured in/out of tolerance; "Auto · nominal" chips. */
export function QcReadingsTable({ fields, values, auto, onChange }: {
  fields: QcField[]; values: Record<string, string>; auto: Set<string>; onChange: (key: string, value: string) => void;
}) {
  if (fields.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[460px] border-collapse text-[13px]">
        <thead>
          <tr className="bg-subtle text-[11px] tracking-[0.4px] text-fg-muted uppercase">
            <th className="rounded-l-lg px-2.5 py-2 text-left font-semibold">Reading</th>
            <th className="px-2.5 py-2 text-left font-semibold">Spec</th>
            <th className="px-2.5 py-2 text-left font-semibold">Observed</th>
            <th className="rounded-r-lg px-2.5 py-2 text-left font-semibold">Result</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f) => {
            const v = values[f.key] ?? "";
            const ok = evaluateReading(f, v);
            const type = (f.type ?? "NUMBER").toUpperCase();
            return (
              <tr key={f.key} className="border-b border-line">
                <td className="px-2.5 py-2 font-medium text-fg">{f.label}{f.required ? <span className="text-danger"> *</span> : null}</td>
                <td className="px-2.5 py-2 text-fg-muted">{toleranceHint(f)}</td>
                <td className="px-2.5 py-2">
                  <div className="flex items-center gap-2">
                    {type === "BOOL" ? (
                      <select aria-label={f.label} value={v} onChange={(e) => onChange(f.key, e.target.value)} className="h-9 rounded-lg border border-line bg-surface px-2 text-[13px]">
                        <option value="">—</option><option value="true">Yes</option><option value="false">No</option>
                      </select>
                    ) : (
                      <Input aria-label={f.label} className={cn("h-9 w-32", ok === false && "border-danger text-danger-text", ok === true && "border-success")}
                        inputMode={type === "NUMBER" ? "decimal" : undefined} value={v} onChange={(e) => onChange(f.key, e.target.value)} suffix={f.unit ?? undefined} />
                    )}
                    {auto.has(f.key) ? <span className="rounded-md bg-sky-tint px-1.5 py-0.5 text-[10.5px] font-semibold text-sky-text">Auto · nominal</span> : null}
                  </div>
                </td>
                <td className="px-2.5 py-2">
                  {ok === null ? <span className="text-fg-faint">—</span> : ok ? <span className="font-semibold text-success-text">Pass</span> : <span className="font-semibold text-danger-text">Out of tolerance</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
