import { cn } from "@/lib/utils";

type Json = null | boolean | number | string | Json[] | { [k: string]: Json };

export interface DiffRow {
  path: string;
  kind: "added" | "removed" | "changed";
  before?: Json;
  after?: Json;
}

function isObj(v: unknown): v is Record<string, Json> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Flatten two JSON values into a list of leaf-level differences. Pure & tested. */
export function diffJson(before: unknown, after: unknown, base = ""): DiffRow[] {
  const b = before as Json | undefined;
  const a = after as Json | undefined;
  if (isObj(b) && isObj(a)) {
    const keys = Array.from(new Set([...Object.keys(b), ...Object.keys(a)])).sort();
    return keys.flatMap((k) => diffJson(b[k], a[k], base ? `${base}.${k}` : k));
  }
  if (Array.isArray(b) && Array.isArray(a)) {
    const n = Math.max(b.length, a.length);
    return Array.from({ length: n }, (_, i) => diffJson(b[i], a[i], `${base}[${i}]`)).flat();
  }
  if (b === undefined && a === undefined) return [];
  if (b === undefined) return [{ path: base || "(root)", kind: "added", after: a }];
  if (a === undefined) return [{ path: base || "(root)", kind: "removed", before: b }];
  if (JSON.stringify(b) === JSON.stringify(a)) return [];
  return [{ path: base || "(root)", kind: "changed", before: b, after: a }];
}

const fmt = (v: Json | undefined) => (v === undefined ? "" : typeof v === "string" ? v : JSON.stringify(v));

/** Before/after viewer for audit logs. Renders values as text only (no HTML). */
export function JsonDiff({ before, after, className }: { before: unknown; after: unknown; className?: string }) {
  const rows = diffJson(before ?? undefined, after ?? undefined);
  if (rows.length === 0) return <p className="text-[12.5px] text-fg-muted">No field-level changes recorded.</p>;
  return (
    <div className={cn("overflow-x-auto rounded-xl border border-line", className)}>
      <table className="w-full border-collapse font-mono text-[12px]">
        <thead>
          <tr className="bg-subtle text-left text-[11px] tracking-[0.4px] text-fg-muted">
            <th scope="col" className="px-3 py-2 font-semibold">FIELD</th>
            <th scope="col" className="px-3 py-2 font-semibold">BEFORE</th>
            <th scope="col" className="px-3 py-2 font-semibold">AFTER</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.path} className="border-t border-line align-top">
              <td className="px-3 py-2 font-semibold whitespace-nowrap text-fg">{r.path}</td>
              <td className={cn("px-3 py-2 break-all", r.kind !== "added" && "bg-danger-tint text-danger-text")}>{r.kind === "added" ? "—" : `− ${fmt(r.before)}`}</td>
              <td className={cn("px-3 py-2 break-all", r.kind !== "removed" && "bg-success-tint text-success-text")}>{r.kind === "removed" ? "—" : `+ ${fmt(r.after)}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Pretty-printed raw JSON block (text only). */
export function JsonBlock({ value, className }: { value: unknown; className?: string }) {
  return <pre className={cn("max-h-80 overflow-auto rounded-xl bg-subtle p-3 font-mono text-[12px] text-fg", className)}>{value === null || value === undefined ? "—" : JSON.stringify(value, null, 2)}</pre>;
}
