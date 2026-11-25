import { describe, expect, it } from "vitest";
import { emptyItem, itemSchema, toItemIn } from "./item-schema";

describe("stock item schema", () => {
  it("maps custom fields and BOM", () => {
    const v = itemSchema.parse({
      ...emptyItem("Flange 80NB"), hsn_sac_code: "7307", opening_qty: "10", opening_rate: "1443",
      custom_fields: [{ key: "Material Grade", value: "SS304" }, { key: "", value: "x" }],
      bom: [{ raw_item_id: "rm", qty_per_unit: "2.5", scrap_pct: "" }, { raw_item_id: "", qty_per_unit: "1", scrap_pct: "" }],
    });
    const body = toItemIn(v);
    expect(body.custom_fields).toEqual({ "Material Grade": "SS304" });
    expect(body.bom_components).toEqual([{ raw_item_id: "rm", qty_per_unit: "2.5", scrap_pct: "0" }]);
    expect(body.uom_conversion_factor).toBeNull();
    expect(body.opening_qty).toBe("10");
  });
  it("validates HSN", () => {
    expect(itemSchema.safeParse({ ...emptyItem("x"), hsn_sac_code: "12" }).success).toBe(false);
  });
});
