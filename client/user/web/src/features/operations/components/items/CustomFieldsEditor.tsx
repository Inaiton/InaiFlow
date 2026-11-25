"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button, Field, FieldRow, Input, NativeSelect } from "@/components/ui";
import { toKey, type FieldDef, type FieldType, type ItemFieldsValue } from "./item-fields";

/** Typed custom fields (design Ops-Item-Fields): label → key used in report tokens. */
export function CustomFieldsEditor({ value, onChange }: { value: ItemFieldsValue; onChange: (v: ItemFieldsValue) => void }) {
  const [label, setLabel] = useState("");
  const [type, setType] = useState<FieldType>("TEXT");
  const add = () => {
    const key = toKey(label);
    if (!key || value.defs.some((d) => d.key === key)) return;
    onChange({ ...value, defs: [...value.defs, { key, label: label.trim(), type }] });
    setLabel("");
  };
  const setVal = (k: string, v: string) => onChange({ ...value, values: { ...value.values, [k]: v } });
  const patchDef = (k: string, p: Partial<FieldDef>) => onChange({ ...value, defs: value.defs.map((d) => (d.key === k ? { ...d, ...p } : d)) });
  const remove = (k: string) => {
    const values = { ...value.values };
    delete values[k];
    onChange({ values, defs: value.defs.filter((d) => d.key !== k) });
  };
  return (
    <div className="flex flex-col gap-3">
      {value.defs.map((d) => (
        <div key={d.key} className="grid grid-cols-[1fr_1fr_auto] items-end gap-2 rounded-xl border border-line p-3">
          <Field label={d.label} hint={`Token: {{item.custom.${d.key}}}`}>
            {d.type === "DROPDOWN" ? (
              <NativeSelect value={value.values[d.key] ?? ""} onChange={(e) => setVal(d.key, e.target.value)}>
                <option value="">—</option>
                {(d.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
              </NativeSelect>
            ) : (
              <Input value={value.values[d.key] ?? ""} inputMode={d.type === "NUMBER" ? "decimal" : undefined} suffix={d.unit} onChange={(e) => setVal(d.key, e.target.value)} />
            )}
          </Field>
          {d.type === "DROPDOWN" ? (
            <Field label="Options (comma separated)">
              <Input value={(d.options ?? []).join(", ")} onChange={(e) => patchDef(d.key, { options: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
            </Field>
          ) : d.type === "NUMBER" ? (
            <Field label="Unit"><Input value={d.unit ?? ""} onChange={(e) => patchDef(d.key, { unit: e.target.value || undefined })} /></Field>
          ) : <span />}
          <Button size="icon" variant="ghost" aria-label={`Remove ${d.label}`} onClick={() => remove(d.key)}><Trash2 /></Button>
        </div>
      ))}
      <FieldRow>
        <Field label="New field label" hint={label ? `Key: ${toKey(label)}` : "e.g. Hardness spec"}>
          <Input value={label} onChange={(e) => setLabel(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
        </Field>
        <Field label="Type">
          <NativeSelect value={type} onChange={(e) => setType(e.target.value as FieldType)}>
            <option value="TEXT">Text</option>
            <option value="NUMBER">Number</option>
            <option value="DROPDOWN">Dropdown</option>
          </NativeSelect>
        </Field>
      </FieldRow>
      <div><Button size="sm" onClick={add} disabled={!toKey(label)}><Plus /> Add field</Button></div>
    </div>
  );
}
