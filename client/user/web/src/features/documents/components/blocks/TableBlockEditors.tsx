"use client";

import { Plus, X } from "lucide-react";
import { Button, Input } from "@/components/ui";
import { cn } from "@/lib/utils";
import { qcRows, tableColumns, tableRows, text, type QcRow } from "../../lib/blocks";
import type { EditorProps } from "./SimpleBlockEditors";

export function TableEditor({ block, onChange }: EditorProps) {
  const cols = tableColumns(block);
  const rows = tableRows(block);
  const save = (c: string[], r: string[][]) => onChange({ columns: c, rows: r });
  return (
    <div className="flex flex-col gap-1.5 overflow-x-auto">
      <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${cols.length}, minmax(110px, 1fr)) 32px` }}>
        {cols.map((c, i) => <Input key={`h${i}`} aria-label={`Column ${i + 1}`} className="font-semibold" value={c} onChange={(e) => save(cols.map((x, j) => (j === i ? e.target.value : x)), rows)} />)}
        <Button size="icon-sm" variant="ghost" aria-label="Add column" onClick={() => save([...cols, `Column ${cols.length + 1}`], rows.map((r) => [...r, ""]))}><Plus /></Button>
        {rows.map((r, i) => (
          <div key={`r${i}`} className="contents">
            {cols.map((_, j) => <Input key={j} aria-label={`Row ${i + 1} ${cols[j]}`} value={r[j] ?? ""} onChange={(e) => save(cols, rows.map((x, k) => (k === i ? cols.map((__, m) => (m === j ? e.target.value : (x[m] ?? ""))) : x)))} />)}
            <Button size="icon-sm" variant="ghost" aria-label="Remove row" onClick={() => save(cols, rows.filter((_, k) => k !== i))}><X /></Button>
          </div>
        ))}
      </div>
      <Button size="sm" variant="ghost" className="self-start" onClick={() => save(cols, [...rows, cols.map(() => "")])}><Plus /> Row</Button>
    </div>
  );
}

/** QC readings table: nominal-filled values stay editable; typing a real reading clears the AUTO tag. */
export function QcTableEditor({ block, onChange }: EditorProps) {
  const rows = qcRows(block);
  const base = (block.data && typeof block.data === "object" ? block.data : {}) as Record<string, unknown>;
  const save = (r: QcRow[]) => onChange({ ...base, rows: r });
  const patch = (i: number, p: Partial<QcRow>) => save(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  if (rows.length === 0 && text(block)) return <p className="m-0 text-xs text-fg-muted">Readings come from the linked step ({text(block)}). Add rows to type them yourself.</p>;
  return (
    <div className="flex flex-col gap-1.5 overflow-x-auto">
      <div className="grid min-w-[560px] grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_90px_32px] gap-1.5 text-[11px] font-semibold tracking-wide text-fg-muted uppercase">
        <span>Parameter</span><span>Spec</span><span>Observed</span><span>Result</span><span />
      </div>
      {rows.map((r, i) => (
        <div key={i} className="grid min-w-[560px] grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_90px_32px] items-center gap-1.5">
          <Input aria-label="Parameter" value={r.parameter} onChange={(e) => patch(i, { parameter: e.target.value })} />
          <Input aria-label="Spec" value={r.spec} onChange={(e) => patch(i, { spec: e.target.value })} />
          <div className="relative">
            <Input aria-label={`Observed ${r.parameter}`} className={cn(r.auto && "pr-14 text-fg-muted")} value={r.observed} onChange={(e) => patch(i, { observed: e.target.value, auto: false })} />
            {r.auto ? <span className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 rounded bg-sky-tint px-1 text-[10px] font-semibold text-sky-text">AUTO</span> : null}
          </div>
          <select aria-label="Result" value={r.result} onChange={(e) => patch(i, { result: e.target.value })} className={cn("h-10 rounded-lg border border-line bg-surface px-2 text-[13px]", r.result === "Fail" && "text-danger-text", r.result === "Pass" && "text-success-text")}>
            <option value="">—</option><option>Pass</option><option>Fail</option>
          </select>
          <Button size="icon-sm" variant="ghost" aria-label="Remove reading" onClick={() => save(rows.filter((_, j) => j !== i))}><X /></Button>
        </div>
      ))}
      <Button size="sm" variant="ghost" className="self-start" onClick={() => save([...rows, { parameter: "", spec: "", observed: "", auto: false, result: "" }])}><Plus /> Reading</Button>
    </div>
  );
}
