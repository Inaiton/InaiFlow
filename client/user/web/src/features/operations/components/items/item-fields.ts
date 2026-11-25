/**
 * Item `custom_fields` JSON layout (decision W3-4): flat `key → value` strings so report tokens
 * `{{item.custom.<key>}}` resolve directly, plus `_defs` describing user-added typed fields.
 */
export type FieldType = "TEXT" | "NUMBER" | "DROPDOWN";
export interface FieldDef { key: string; label: string; type: FieldType; unit?: string; options?: string[] }
export interface ItemFieldsValue { values: Record<string, string>; defs: FieldDef[] }

/** Standard spec keys shown as first-class inputs. */
export const SPEC_KEYS = ["material_grade", "drawing_rev", "tolerance", "cycle_time_min"] as const;

export function readFields(json: unknown): ItemFieldsValue {
  const o = json && typeof json === "object" && !Array.isArray(json) ? (json as Record<string, unknown>) : {};
  const values: Record<string, string> = {};
  for (const [k, v] of Object.entries(o)) if (k !== "_defs" && (typeof v === "string" || typeof v === "number")) values[k] = String(v);
  const defs = Array.isArray(o._defs)
    ? o._defs.flatMap((d): FieldDef[] => {
        if (!d || typeof d !== "object") return [];
        const r = d as Record<string, unknown>;
        if (typeof r.key !== "string" || typeof r.label !== "string") return [];
        const type: FieldType = r.type === "NUMBER" || r.type === "DROPDOWN" ? r.type : "TEXT";
        return [{ key: r.key, label: r.label, type, unit: typeof r.unit === "string" ? r.unit : undefined, options: Array.isArray(r.options) ? r.options.map(String) : undefined }];
      })
    : [];
  return { values, defs };
}

export function writeFields(v: ItemFieldsValue): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, val] of Object.entries(v.values)) if (val.trim() !== "") out[k] = val.trim();
  if (v.defs.length) out._defs = v.defs;
  return out;
}

export const toKey = (label: string) => label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 40);
