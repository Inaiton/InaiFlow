import { describe, expect, it } from "vitest";
import { countOutOfTolerance, evaluateReading, limits, missingRequired, quickQcAutofill, toleranceHint, type QcField } from "./tolerance";

const bore: QcField = { key: "bore", label: "Bore", type: "NUMBER", unit: "mm", nominal: "40.00", tol_minus: "0.02", tol_plus: "0.02", required: true };
const ra: QcField = { key: "ra", label: "Ra", type: "NUMBER", nominal: "1.6", tol_minus: null, tol_plus: "0.2" };
const visual: QcField = { key: "visual", label: "Visual OK", type: "BOOL", required: true };
const heat: QcField = { key: "heat", label: "Heat no", type: "TEXT", required: true };

describe("tolerance", () => {
  it("computes limits exactly", () => {
    expect(limits(bore)).toEqual({ lower: "39.98", upper: "40.02" });
    expect(limits(ra)).toEqual({ lower: null, upper: "1.8" });
    expect(limits(heat)).toBeNull();
  });
  it("evaluates numeric readings at the boundaries", () => {
    expect(evaluateReading(bore, "40.02")).toBe(true);
    expect(evaluateReading(bore, "39.98")).toBe(true);
    expect(evaluateReading(bore, "40.021")).toBe(false);
    expect(evaluateReading(bore, "39.979")).toBe(false);
    expect(evaluateReading(bore, "abc")).toBe(false);
    expect(evaluateReading(bore, "")).toBeNull();
    expect(evaluateReading(ra, "0.1")).toBe(true);
  });
  it("evaluates bool / text / options", () => {
    expect(evaluateReading(visual, "yes")).toBe(true);
    expect(evaluateReading(visual, "No")).toBe(false);
    expect(evaluateReading(heat, "H-22")).toBeNull();
    expect(evaluateReading({ key: "c", label: "C", type: "SELECT", options: ["A", "B"] }, "C")).toBe(false);
  });
  it("formats hints", () => {
    expect(toleranceHint(bore)).toBe("40.00 ± 0.02 mm");
    expect(toleranceHint(ra)).toBe("1.6 −0 / +0.2");
    expect(toleranceHint(visual)).toBe("Yes / No");
  });
  it("quick QC fills nominals only where empty", () => {
    const r = quickQcAutofill([bore, ra, visual], { ra: "1.7" });
    expect(r.bore).toEqual({ value: "40.00", autoFilled: true });
    expect(r.ra).toEqual({ value: "1.7", autoFilled: false });
    expect(r.visual).toEqual({ value: "", autoFilled: false });
  });
  it("finds missing required fields and out-of-tolerance count", () => {
    expect(missingRequired([bore, visual, heat], {}, true).map((f) => f.key)).toEqual(["visual", "heat"]);
    expect(missingRequired([bore], {}, false).map((f) => f.key)).toEqual(["bore"]);
    expect(countOutOfTolerance([bore, ra], { bore: "41", ra: "1.6" })).toBe(1);
  });
});
