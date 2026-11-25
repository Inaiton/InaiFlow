import type { components } from "@/lib/api/schema";

export type Block = components["schemas"]["ReportBlock"];
export const BLOCK_TYPES = ["heading", "paragraph", "kv", "table", "qc_table", "signature", "checklist", "divider"] as const;
/** Legacy / alternate names accepted on read (task brief used kv_table / qc_readings; server seeds use kv / qc_table). */
export const BLOCK_ALIASES: Record<string, BlockType> = { kv_table: "kv", qc_readings: "qc_table" };
export function canonicalType(t: string): string {
  return BLOCK_ALIASES[t] ?? t;
}
export type BlockType = (typeof BLOCK_TYPES)[number];
export const BLOCK_LABEL: Record<BlockType, string> = {
  heading: "Heading",
  paragraph: "Paragraph",
  kv: "Key–value table",
  table: "Table",
  qc_table: "QC readings",
  signature: "Signatures",
  checklist: "Checklist",
  divider: "Divider",
};

export function defaultData(t: BlockType): Record<string, unknown> {
  switch (t) {
    case "heading":
      return { text: "", level: 2 };
    case "paragraph":
      return { text: "" };
    case "kv":
      return { rows: [{ label: "Item", value: "{{item.name}}" }] };
    case "table":
      return { columns: ["Column 1", "Column 2"], rows: [["", ""]] };
    case "qc_table":
      return { source: "step", text: "{{step.qc_readings}}" };
    case "signature":
      return { roles: ["Prepared by", "Approved by"] };
    case "checklist":
      return { items: [""] };
    default:
      return {};
  }
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isBlocks = (v: unknown): v is Block[] => Array.isArray(v) && v.every((b) => isObj(b) && typeof b.id === "string" && typeof b.type === "string");

/** Report template payload: `{ blocks }` or `{ ..., content_schema: { blocks } }`. */
export function extractBlocks(payload: unknown): { blocks: Block[]; wrap: (b: Block[]) => unknown } | null {
  if (!isObj(payload)) return null;
  if (isBlocks(payload.blocks)) return { blocks: payload.blocks, wrap: (blocks) => ({ ...payload, blocks }) };
  const cs = payload.content_schema;
  if (isObj(cs) && isBlocks(cs.blocks)) return { blocks: cs.blocks, wrap: (blocks) => ({ ...payload, content_schema: { ...cs, blocks } }) };
  return null;
}

export function newBlockId(blocks: Block[]): string {
  let i = blocks.length + 1;
  while (blocks.some((b) => b.id === `b${i}`)) i++;
  return `b${i}`;
}
