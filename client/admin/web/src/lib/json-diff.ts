export type DiffKind = "added" | "removed" | "changed";
export interface DiffEntry {
  path: string;
  kind: DiffKind;
  before?: unknown;
  after?: unknown;
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Structural diff of two JSON values; returns leaf-level changes with dotted/indexed paths. */
export function diffJson(before: unknown, after: unknown, path = ""): DiffEntry[] {
  if (Object.is(before, after)) return [];
  if (Array.isArray(before) && Array.isArray(after)) {
    const out: DiffEntry[] = [];
    const n = Math.max(before.length, after.length);
    for (let i = 0; i < n; i++) {
      const p = `${path}[${i}]`;
      if (i >= before.length) out.push({ path: p, kind: "added", after: after[i] });
      else if (i >= after.length) out.push({ path: p, kind: "removed", before: before[i] });
      else out.push(...diffJson(before[i], after[i], p));
    }
    return out;
  }
  if (isObj(before) && isObj(after)) {
    const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort();
    return keys.flatMap((k) => {
      const p = path ? `${path}.${k}` : k;
      if (!(k in before)) return [{ path: p, kind: "added" as const, after: after[k] }];
      if (!(k in after)) return [{ path: p, kind: "removed" as const, before: before[k] }];
      return diffJson(before[k], after[k], p);
    });
  }
  if (before === undefined || before === null) {
    if (after === undefined) return [];
    return [{ path: path || "(root)", kind: before === null ? "changed" : "added", before, after }];
  }
  if (after === undefined) return [{ path: path || "(root)", kind: "removed", before }];
  return [{ path: path || "(root)", kind: "changed", before, after }];
}

export function previewValue(v: unknown): string {
  if (v === undefined) return "";
  const s = JSON.stringify(v);
  return s.length > 120 ? `${s.slice(0, 117)}...` : s;
}
