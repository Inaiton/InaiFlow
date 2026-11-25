import type { Schemas } from "@/core/api/types";

/**
 * Structured report blocks (server seeds/doc_templates.py + export adapter). Block `data` is JSON
 * from the API, so every reader is defensive. Rendering is React-only — never inject HTML.
 */
export type ReportBlock = Schemas["ReportBlock"];

export type BlockType = "heading" | "paragraph" | "kv" | "table" | "qc_table" | "checklist" | "signature" | "image" | "divider" | "page_break";

export interface KvRow { label: string; value: string }
export interface QcRow { parameter: string; spec: string; observed: string; auto: boolean; result: string }
export interface CheckItem { label: string; checked: boolean }

export const BLOCK_LABELS: Record<BlockType, string> = {
  heading: "Heading",
  paragraph: "Paragraph",
  kv: "Details table",
  table: "Table",
  qc_table: "QC readings",
  checklist: "Checklist",
  signature: "Signatures",
  image: "Image",
  divider: "Divider",
  page_break: "Page break",
};

const rec = (d: unknown): Record<string, unknown> => (d && typeof d === "object" && !Array.isArray(d) ? (d as Record<string, unknown>) : {});
const str = (v: unknown): string => (typeof v === "string" ? v : typeof v === "number" || typeof v === "boolean" ? String(v) : "");
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);

export const text = (b: ReportBlock) => str(rec(b.data).text);
export const level = (b: ReportBlock): 1 | 2 | 3 => {
  const l = Number(rec(b.data).level);
  return l === 1 || l === 3 ? l : 2;
};
export const kvRows = (b: ReportBlock): KvRow[] => arr(rec(b.data).rows).map((r) => ({ label: str(rec(r).label), value: str(rec(r).value) }));
export const tableColumns = (b: ReportBlock): string[] => arr(rec(b.data).columns).map(str);
export const tableRows = (b: ReportBlock): string[][] => arr(rec(b.data).rows).map((r) => arr(r).map(str));
export const checkItems = (b: ReportBlock): CheckItem[] => arr(rec(b.data).items).map((i) => ({ label: str(rec(i).label), checked: rec(i).checked === true }));
export const signatureRoles = (b: ReportBlock): string[] => arr(rec(b.data).roles).map(str);
export const imageData = (b: ReportBlock) => ({ documentId: str(rec(b.data).document_id) || null, caption: str(rec(b.data).caption) });

/** QC rows: structured `rows` objects, or legacy `columns/rows` arrays; empty when only `text` exists. */
export function qcRows(b: ReportBlock): QcRow[] {
  return arr(rec(b.data).rows).map((r) => {
    if (Array.isArray(r)) return { parameter: str(r[0]), spec: str(r[1]), observed: str(r[2]), auto: /auto/i.test(str(r[3])), result: str(r[4] ?? r[3]) };
    const o = rec(r);
    return { parameter: str(o.parameter ?? o.label), spec: str(o.spec), observed: str(o.observed ?? o.value), auto: o.auto === true || o.auto_filled === true, result: str(o.result) };
  });
}

let seq = 0;
export const newBlockId = () => `b-${Date.now().toString(36)}-${(seq++).toString(36)}`;

export function emptyBlock(type: BlockType): ReportBlock {
  const id = newBlockId();
  switch (type) {
    case "heading": return { id, type, data: { text: "", level: 2 } };
    case "paragraph": return { id, type, data: { text: "" } };
    case "kv": return { id, type, data: { rows: [{ label: "", value: "" }] } };
    case "table": return { id, type, data: { columns: ["Column 1", "Column 2"], rows: [["", ""]] } };
    case "qc_table": return { id, type, data: { source: "step", rows: [] } };
    case "checklist": return { id, type, data: { items: [{ label: "", checked: false }] } };
    case "signature": return { id, type, data: { roles: ["Inspected by", "Approved by"] } };
    case "image": return { id, type, data: { document_id: null, caption: "" } };
    default: return { id, type, data: {} };
  }
}

/** Parse unknown JSON (`{blocks:[…]}` or `[…]`) into blocks with unique ids. */
export function normalizeBlocks(json: unknown): ReportBlock[] {
  const list = Array.isArray(json) ? json : arr(rec(json).blocks);
  const seen = new Set<string>();
  return list.flatMap((raw) => {
    const o = rec(raw);
    const type = str(o.type);
    if (!type) return [];
    let id = str(o.id) || newBlockId();
    if (seen.has(id)) id = newBlockId();
    seen.add(id);
    return [{ id, type, data: o.data ?? {} }];
  });
}

export type BlockAction =
  | { type: "replace"; blocks: ReportBlock[] }
  | { type: "add"; block: ReportBlock; afterId?: string | null }
  | { type: "remove"; id: string }
  | { type: "move"; id: string; dir: -1 | 1 }
  | { type: "update"; id: string; data: unknown };

export function blocksReducer(state: ReportBlock[], a: BlockAction): ReportBlock[] {
  switch (a.type) {
    case "replace":
      return a.blocks;
    case "add": {
      if (!a.afterId) return [...state, a.block];
      const i = state.findIndex((b) => b.id === a.afterId);
      if (i < 0) return [...state, a.block];
      return [...state.slice(0, i + 1), a.block, ...state.slice(i + 1)];
    }
    case "remove":
      return state.filter((b) => b.id !== a.id);
    case "move": {
      const i = state.findIndex((b) => b.id === a.id);
      const j = i + a.dir;
      if (i < 0 || j < 0 || j >= state.length) return state;
      const next = [...state];
      [next[i], next[j]] = [next[j]!, next[i]!];
      return next;
    }
    case "update":
      return state.map((b) => (b.id === a.id ? { ...b, data: a.data } : b));
  }
}

/** Distinct `{{tokens}}` used anywhere in the blocks (for template builder hints). */
export function tokensIn(blocks: ReportBlock[]): string[] {
  const found = new Set<string>();
  const walk = (v: unknown) => {
    if (typeof v === "string") for (const m of v.matchAll(/\{\{\s*([\w.]+)\s*\}\}/g)) found.add(m[1]!);
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === "object") Object.values(v).forEach(walk);
  };
  blocks.forEach((b) => walk(b.data));
  return [...found].sort();
}
