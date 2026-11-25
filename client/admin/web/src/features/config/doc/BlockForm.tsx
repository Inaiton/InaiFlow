"use client";

import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { canonicalType, type Block } from "./blocks";

type D = Record<string, unknown>;
const str = (v: unknown) => (typeof v === "string" ? v : "");
const strArr = (v: unknown): string[] => (Array.isArray(v) ? v.map((x) => (typeof x === "string" ? x : "")) : []);

/** Appends a token to the block's primary text field. */
export function insertToken(block: Block, token: string): D {
  const d = (block.data ?? {}) as D;
  switch (canonicalType(block.type)) {
    case "heading":
    case "paragraph":
    case "qc_table":
      return { ...d, text: `${str(d.text)}${token}` };
    case "kv": {
      const rows = Array.isArray(d.rows) ? (d.rows as D[]) : [];
      return { ...d, rows: [...rows, { label: "", value: token }] };
    }
    case "checklist":
      return { ...d, items: [...strArr(d.items), token] };
    default:
      return d;
  }
}

export function BlockForm({ block, onChange, readOnly }: { block: Block; onChange: (data: D) => void; readOnly: boolean }) {
  const d = (block.data ?? {}) as D;
  const set = (patch: D) => onChange({ ...d, ...patch });
  switch (canonicalType(block.type)) {
    case "heading":
      return (
        <div className="flex gap-2">
          <NativeSelect className="w-24" value={String(d.level ?? 2)} disabled={readOnly} onChange={(e) => set({ level: Number(e.target.value) })} aria-label="Heading level">
            <option value="1">H1</option>
            <option value="2">H2</option>
            <option value="3">H3</option>
          </NativeSelect>
          <Input value={str(d.text)} disabled={readOnly} onChange={(e) => set({ text: e.target.value })} placeholder="Heading text" />
        </div>
      );
    case "paragraph":
      return <Textarea value={str(d.text)} disabled={readOnly} onChange={(e) => set({ text: e.target.value })} placeholder="Text with {{tokens}}" />;
    case "qc_table":
      return (
        <div className="space-y-1">
          <Input value={str(d.text)} disabled={readOnly} onChange={(e) => set({ text: e.target.value })} placeholder="{{step.qc_readings}}" />
          <p className="text-xs text-faint">Renders the step&apos;s QC fields, nominal, tolerance and readings ({"{{step.qc_readings}}"}).</p>
        </div>
      );
    case "kv": {
      const rows = Array.isArray(d.rows) ? (d.rows as D[]) : [];
      const setRows = (r: D[]) => set({ rows: r });
      return (
        <div className="space-y-1.5">
          {rows.map((r, i) => (
            <div key={i} className="flex gap-2">
              <Input className="w-1/3" value={str(r.label)} disabled={readOnly} placeholder="Label" onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />
              <Input value={str(r.value)} disabled={readOnly} placeholder="Value / {{token}}" onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))} />
              {!readOnly ? (
                <Button variant="ghost" size="icon" aria-label="Remove row" onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                  <X />
                </Button>
              ) : null}
            </div>
          ))}
          {!readOnly ? (
            <Button size="sm" variant="ghost" onClick={() => setRows([...rows, { label: "", value: "" }])}>
              <Plus /> Row
            </Button>
          ) : null}
        </div>
      );
    }
    case "table": {
      const cols = strArr(d.columns);
      const rows = Array.isArray(d.rows) ? (d.rows as unknown[]).map(strArr) : [];
      return (
        <div className="space-y-1.5">
          <Input value={cols.join(", ")} disabled={readOnly} onChange={(e) => set({ columns: e.target.value.split(",").map((c) => c.trim()) })} placeholder="Columns, comma separated" aria-label="Columns" />
          {rows.map((r, i) => (
            <div key={i} className="flex gap-1.5">
              {cols.map((_, ci) => (
                <Input key={ci} className="h-8 text-[13px]" value={r[ci] ?? ""} disabled={readOnly} aria-label={`Row ${i + 1} ${cols[ci]}`} onChange={(e) => set({ rows: rows.map((x, j) => (j === i ? cols.map((__, k) => (k === ci ? e.target.value : (x[k] ?? ""))) : x)) })} />
              ))}
              {!readOnly ? (
                <Button variant="ghost" size="icon" aria-label="Remove row" onClick={() => set({ rows: rows.filter((_, j) => j !== i) })}>
                  <X />
                </Button>
              ) : null}
            </div>
          ))}
          {!readOnly ? (
            <Button size="sm" variant="ghost" onClick={() => set({ rows: [...rows, cols.map(() => "")] })}>
              <Plus /> Row
            </Button>
          ) : null}
        </div>
      );
    }
    case "signature":
      return <Input value={strArr(d.roles).join(", ")} disabled={readOnly} onChange={(e) => set({ roles: e.target.value.split(",").map((s) => s.trim()) })} placeholder="Prepared by, Reviewed by, Approved by" aria-label="Signature roles" />;
    case "checklist":
      return <Textarea value={strArr(d.items).join("\n")} disabled={readOnly} onChange={(e) => set({ items: e.target.value.split("\n") })} placeholder="One item per line" aria-label="Checklist items" />;
    case "divider":
      return <hr className="border-line" />;
    default:
      return <p className="text-xs text-faint">Unknown block type “{block.type}” — preserved as-is.</p>;
  }
}
