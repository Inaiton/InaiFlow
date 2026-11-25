import { z } from "zod";
import type { Schemas } from "@/core/api/types";
import { isDecimal } from "@/core/money";

const dec = z.string().trim().refine((v) => v === "" || isDecimal(v), "Enter a number");

export const VALUATION_METHODS = [
  { value: "WEIGHTED_AVG", label: "Weighted average" },
  { value: "FIFO", label: "FIFO" },
  { value: "LIFO", label: "LIFO" },
  { value: "STANDARD", label: "Standard cost" },
];

export const itemSchema = z.object({
  target_type: z.enum(["STOCK_ITEM", "STANDALONE_PROCESS"]),
  name: z.string().trim().min(1, "Name is required").max(200),
  sku_code: z.string().trim(),
  stock_group_id: z.string(),
  uom_primary: z.string().min(1, "Choose a unit"),
  uom_alternate: z.string(),
  uom_conversion_factor: dec,
  valuation_method: z.string(),
  hsn_sac_code: z.string().trim().refine((v) => v === "" || /^\d{4,8}$/.test(v), "4–8 digit HSN/SAC"),
  gst_rate: dec,
  opening_qty: dec,
  opening_rate: dec,
  reorder_level: dec,
  custom_fields: z.array(z.object({ key: z.string().trim(), value: z.string() })),
  bom: z.array(z.object({ raw_item_id: z.string(), qty_per_unit: dec, scrap_pct: dec })),
  diagram_storage_key: z.string().nullable(),
});

export type ItemForm = z.input<typeof itemSchema>;
export type ItemValues = z.output<typeof itemSchema>;

export const emptyItem = (name = ""): ItemForm => ({
  target_type: "STOCK_ITEM", name, sku_code: "", stock_group_id: "", uom_primary: "Nos", uom_alternate: "", uom_conversion_factor: "",
  valuation_method: "WEIGHTED_AVG", hsn_sac_code: "", gst_rate: "18", opening_qty: "", opening_rate: "", reorder_level: "", custom_fields: [], bom: [],
  diagram_storage_key: null,
});

/** Form → StockItemIn. Custom fields become a JSON object; empty BOM rows are dropped. */
export function toItemIn(v: ItemValues): Schemas["StockItemIn"] {
  const custom: Record<string, string> = {};
  for (const f of v.custom_fields) if (f.key) custom[f.key] = f.value;
  return {
    target_type: v.target_type, name: v.name, sku_code: v.sku_code || null, stock_group_id: v.stock_group_id || null, uom_primary: v.uom_primary,
    uom_alternate: v.uom_alternate || null, uom_conversion_factor: v.uom_alternate && v.uom_conversion_factor ? v.uom_conversion_factor : null,
    valuation_method: v.valuation_method, hsn_sac_code: v.hsn_sac_code || null, gst_rate: v.gst_rate || "0", opening_qty: v.opening_qty || "0",
    opening_rate: v.opening_rate || "0", reorder_level: v.reorder_level || null, custom_fields: custom,
    bom_components: v.bom.filter((b) => b.raw_item_id && b.qty_per_unit).map((b) => ({ raw_item_id: b.raw_item_id, qty_per_unit: b.qty_per_unit, scrap_pct: b.scrap_pct || "0" })),
    ...(v.diagram_storage_key ? { diagram_storage_key: v.diagram_storage_key } : {}),
  };
}

export function fromItem(i: Schemas["StockItemOut"]): ItemForm {
  const cf = i.custom_fields && typeof i.custom_fields === "object" && !Array.isArray(i.custom_fields) ? (i.custom_fields as Record<string, unknown>) : {};
  return {
    target_type: i.target_type === "STANDALONE_PROCESS" ? "STANDALONE_PROCESS" : "STOCK_ITEM", name: i.name, sku_code: i.sku_code ?? "", stock_group_id: i.stock_group_id ?? "",
    uom_primary: i.uom_primary, uom_alternate: i.uom_alternate ?? "", uom_conversion_factor: i.uom_conversion_factor ?? "", valuation_method: i.valuation_method,
    hsn_sac_code: i.hsn_sac_code ?? "", gst_rate: i.gst_rate, opening_qty: i.opening_qty === "0" ? "" : i.opening_qty, opening_rate: i.opening_rate === "0" ? "" : i.opening_rate,
    reorder_level: i.reorder_level ?? "", custom_fields: Object.entries(cf).map(([key, value]) => ({ key, value: String(value ?? "") })),
    bom: i.bom_components.map((b) => ({ raw_item_id: b.raw_item_id, qty_per_unit: b.qty_per_unit, scrap_pct: b.scrap_pct })), diagram_storage_key: null,
  };
}
