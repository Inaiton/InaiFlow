"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button, Input, NativeSelect } from "@/components/ui";
import { toleranceHint, type QcField } from "../../lib/tolerance";

const keyOf = (label: string) => label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 40);

/** QC fields of a step: label, type, unit, nominal and ± tolerance. Decimal values stay strings. */
export function QcFieldsEditor({ value, onChange, readOnly }: { value: QcField[]; onChange: (v: QcField[]) => void; readOnly?: boolean }) {
  const patch = (i: number, p: Partial<QcField>) => onChange(value.map((f, j) => (j === i ? { ...f, ...p } : f)));
  const dec = (s: string) => (s.trim() === "" ? null : s.trim());
  return (
    <div className="flex flex-col gap-2">
      {value.length === 0 ? <p className="m-0 text-xs text-fg-muted">No readings — operators will only count units.</p> : null}
      {value.map((f, i) => (
        <fieldset key={i} disabled={readOnly} className="flex flex-col gap-2 rounded-xl border border-line p-2.5">
          <div className="flex gap-2">
            <Input aria-label="Reading name" placeholder="Bore diameter" value={f.label} onChange={(e) => patch(i, { label: e.target.value, key: f.key && f.key !== keyOf(f.label) ? f.key : keyOf(e.target.value) })} />
            <NativeSelect aria-label="Type" className="w-28" value={(f.type ?? "NUMBER").toUpperCase()} onChange={(e) => patch(i, { type: e.target.value })}>
              <option value="NUMBER">Number</option>
              <option value="BOOL">Yes / No</option>
              <option value="TEXT">Text</option>
            </NativeSelect>
            {!readOnly ? <Button size="icon" variant="ghost" aria-label="Remove reading" onClick={() => onChange(value.filter((_, j) => j !== i))}><Trash2 /></Button> : null}
          </div>
          {(f.type ?? "NUMBER").toUpperCase() === "NUMBER" ? (
            <div className="grid grid-cols-4 gap-2">
              <Input aria-label="Nominal" placeholder="Nominal" inputMode="decimal" value={f.nominal ?? ""} onChange={(e) => patch(i, { nominal: dec(e.target.value) })} />
              <Input aria-label="Tolerance minus" placeholder="− tol" inputMode="decimal" value={f.tol_minus ?? ""} onChange={(e) => patch(i, { tol_minus: dec(e.target.value) })} />
              <Input aria-label="Tolerance plus" placeholder="+ tol" inputMode="decimal" value={f.tol_plus ?? ""} onChange={(e) => patch(i, { tol_plus: dec(e.target.value) })} />
              <Input aria-label="Unit" placeholder="mm" value={f.unit ?? ""} onChange={(e) => patch(i, { unit: e.target.value || null })} />
            </div>
          ) : null}
          <div className="flex items-center justify-between text-[11.5px] text-fg-muted">
            <span>Key <code>{f.key || "—"}</code> · {toleranceHint(f)}</span>
            <label className="flex items-center gap-1.5">
              <input type="checkbox" checked={f.required ?? false} onChange={(e) => patch(i, { required: e.target.checked })} /> Required
            </label>
          </div>
        </fieldset>
      ))}
      {!readOnly ? (
        <div><Button size="sm" onClick={() => onChange([...value, { key: "", label: "", type: "NUMBER", required: true }])}><Plus /> Add reading</Button></div>
      ) : null}
    </div>
  );
}
