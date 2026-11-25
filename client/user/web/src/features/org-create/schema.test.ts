import { describe, expect, it } from "vitest";
import { defaultOrgValues, orgCreateSchema, panFromGstin, suggestSlug } from "./schema";

describe("org create schema", () => {
  const valid = {
    ...defaultOrgValues(), legal_name: "Arul Precision Components Pvt Ltd", address_line1: "Plot 14, SIDCO", city: "Coimbatore",
    state_code: "33", pincode: "641021", contact_email: "a@b.in", contact_phone: "+91 98430 12345", gstin: "33AAKCA4821M1Z6",
    fy_begins_from: "2026-04-01", books_beginning_from: "2026-04-01", workspace_slug: "arul-precision",
  };
  it("accepts a valid org", () => {
    expect(orgCreateSchema.safeParse(valid).success).toBe(true);
  });
  it("checks GSTIN state prefix and FY ordering", () => {
    expect(orgCreateSchema.safeParse({ ...valid, state_code: "27" }).success).toBe(false);
    expect(orgCreateSchema.safeParse({ ...valid, books_beginning_from: "2026-03-01" }).success).toBe(false);
    expect(orgCreateSchema.safeParse({ ...valid, gst_reg_type: "UNREGISTERED", gstin: "" }).success).toBe(true);
  });
  it("derives slug and PAN", () => {
    expect(suggestSlug("Arul Precision Components Pvt Ltd")).toBe("arul-precision-components");
    expect(panFromGstin("33AAKCA4821M1Z6")).toBe("AAKCA4821M");
    expect(panFromGstin("bad")).toBe("");
  });
});
