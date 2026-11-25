import { describe, expect, it } from "vitest";
import { validatePayload } from "./registry";

describe("validatePayload", () => {
  it("accepts valid GST payload", () => {
    expect(validatePayload("GST_SLABS", { rates: ["0", "18"], cess: { modes: ["AD_VALOREM_PCT"] } })).toBeNull();
  });
  it("rejects non-decimal rates", () => {
    expect(validatePayload("GST_SLABS", { rates: ["18%x"] })).toMatch(/rates.0/);
  });
  it("validates payroll parts by shape", () => {
    expect(validatePayload("PAYROLL_STATUTORY", { gross_ceiling: "21000", employee_rate: "0.75", employer_rate: "3.25" })).toBeNull();
    expect(validatePayload("PAYROLL_STATUTORY", { gross_ceiling: "21,000", employee_rate: "0.75", employer_rate: "3.25" })).toMatch(/gross_ceiling/);
  });
  it("ignores unknown shapes and categories", () => {
    expect(validatePayload("GST_SLABS", { foo: 1 })).toBeNull();
    expect(validatePayload("WHATEVER", { foo: 1 })).toBeNull();
  });
});
