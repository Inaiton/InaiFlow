"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { isDecimalString } from "@/lib/money";
import { cn } from "@/lib/utils";

export type ColType = "text" | "decimal" | "decimalNullable" | "int" | "bool" | "select";
export interface Col {
  key: string;
  label: string;
  type: ColType;
  options?: readonly string[];
  width?: string;
  placeholder?: string;
  mono?: boolean;
}

type Row = Record<string, unknown>;

function Cell({ col, value, onChange, readOnly }: { col: Col; value: unknown; onChange: (v: unknown) => void; readOnly: boolean }) {
  const common = cn("h-8 text-[13px]", col.mono && "font-mono");
  switch (col.type) {
    case "bool":
      return <input type="checkbox" className="size-4 accent-[#C35E49]" checked={value === true} disabled={readOnly} onChange={(e) => onChange(e.target.checked)} aria-label={col.label} />;
    case "select":
      return (
        <NativeSelect className={common} value={String(value ?? "")} disabled={readOnly} onChange={(e) => onChange(e.target.value)} aria-label={col.label}>
          {col.options?.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </NativeSelect>
      );
    case "int":
      return (
        <Input
          className={common}
          inputMode="numeric"
          value={value == null ? "" : String(value)}
          disabled={readOnly}
          aria-label={col.label}
          onChange={(e) => {
            const v = e.target.value.trim();
            onChange(v === "" ? null : /^-?\d+$/.test(v) ? Number.parseInt(v, 10) : v);
          }}
        />
      );
    case "decimal":
    case "decimalNullable": {
      const s = value == null ? "" : String(value);
      const invalid = s === "" ? col.type === "decimal" : !isDecimalString(s);
      return (
        <Input
          className={cn(common, "text-right tabular-nums")}
          inputMode="decimal"
          value={s}
          placeholder={col.placeholder ?? (col.type === "decimalNullable" ? "—" : "0")}
          aria-invalid={invalid}
          disabled={readOnly}
          aria-label={col.label}
          onChange={(e) => {
            const v = e.target.value.replace(/[,\s₹%]/g, "");
            onChange(v === "" && col.type === "decimalNullable" ? null : v);
          }}
        />
      );
    }
    default:
      return <Input className={common} value={String(value ?? "")} placeholder={col.placeholder} disabled={readOnly} onChange={(e) => onChange(e.target.value)} aria-label={col.label} />;
  }
}

/** Editable table over an array of loose row objects. Unknown row keys are preserved. */
export function RowsTable({
  rows,
  columns,
  onChange,
  readOnly,
  newRow,
  addLabel = "Add row",
}: {
  rows: Row[];
  columns: Col[];
  onChange: (rows: Row[]) => void;
  readOnly: boolean;
  newRow: () => Row;
  addLabel?: string;
}) {
  const update = (i: number, key: string, v: unknown) => onChange(rows.map((r, j) => (j === i ? { ...r, [key]: v } : r)));
  return (
    <div className="rounded-md border border-line">
      <Table>
        <THead>
          <TR>
            {columns.map((c) => (
              <TH key={c.key} style={c.width ? { width: c.width } : undefined}>
                {c.label}
              </TH>
            ))}
            {!readOnly ? <TH className="w-10" /> : null}
          </TR>
        </THead>
        <TBody>
          {rows.map((r, i) => (
            <TR key={i}>
              {columns.map((c) => (
                <TD key={c.key} className="px-2 py-1.5">
                  <Cell col={c} value={r[c.key]} readOnly={readOnly} onChange={(v) => update(i, c.key, v)} />
                </TD>
              ))}
              {!readOnly ? (
                <TD className="px-1">
                  <Button variant="ghost" size="icon" aria-label="Remove row" onClick={() => onChange(rows.filter((_, j) => j !== i))}>
                    <Trash2 />
                  </Button>
                </TD>
              ) : null}
            </TR>
          ))}
          {rows.length === 0 ? (
            <TR>
              <TD colSpan={columns.length + 1} className="py-6 text-center text-[13px] text-faint">
                No rows
              </TD>
            </TR>
          ) : null}
        </TBody>
      </Table>
      {!readOnly ? (
        <div className="border-t border-line p-2">
          <Button size="sm" variant="ghost" onClick={() => onChange([...rows, newRow()])}>
            <Plus /> {addLabel}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
