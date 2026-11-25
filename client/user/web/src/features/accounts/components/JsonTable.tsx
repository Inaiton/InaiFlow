import { EmptyState } from "@/components/ui";
import { isDecimal } from "@/core/money";
import { amt, humanize } from "../lib/format";

const isAmountKey = (k: string) => /(amount|value|taxable|tax|igst|cgst|sgst|cess|total|txval|val)$/i.test(k);

function cell(k: string, v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string" && isDecimal(v) && isAmountKey(k)) return amt(v);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Generic table for contract `json[]` rows (GSTR-1 sections, GSTR-3B tables, challan sections). Columns = union of keys. */
export function JsonTable({ rows, label }: { rows: unknown[]; label: string }) {
  const objs = rows.filter((r): r is Record<string, unknown> => typeof r === "object" && r !== null);
  if (objs.length === 0) return <EmptyState title={`No ${label} records`} />;
  const keys = [...new Set(objs.flatMap((o) => Object.keys(o)))];
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12.5px]" aria-label={label}>
        <thead><tr className="border-b border-line bg-subtle">{keys.map((k) => <th key={k} className={`px-3 py-2 font-semibold whitespace-nowrap text-fg-muted ${isAmountKey(k) ? "text-right" : "text-left"}`}>{humanize(k)}</th>)}</tr></thead>
        <tbody>{objs.map((o, i) => <tr key={i} className="border-b border-line/60">{keys.map((k) => <td key={k} className={`px-3 py-1.5 ${isAmountKey(k) ? "text-right tabular" : ""}`}>{cell(k, o[k])}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

/** Key/value view of a json object (GSTR-3B sections). Nested objects render as JsonTable rows. */
export function JsonSection({ value, label }: { value: unknown; label: string }) {
  if (Array.isArray(value)) return <JsonTable rows={value} label={label} />;
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    const flat = entries.every(([, v]) => typeof v !== "object" || v === null);
    if (flat) return <JsonTable rows={[value]} label={label} />;
    return <div className="flex flex-col gap-3">{entries.map(([k, v]) => <div key={k}><p className="px-3 pb-1 text-[12px] font-semibold text-fg-2">{humanize(k)}</p><JsonSection value={v} label={k} /></div>)}</div>;
  }
  return <p className="px-3 text-[12.5px]">{cell(label, value)}</p>;
}
