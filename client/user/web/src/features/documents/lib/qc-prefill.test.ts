import { describe, expect, it } from "vitest";
import { qcRowsFromStep } from "./qc-prefill";

describe("qcRowsFromStep", () => {
  const fields = [
    { key: "bore", label: "Bore", type: "NUMBER", unit: "mm", nominal: "40.00", tol_minus: "0.02", tol_plus: "0.02" },
    { key: "ra", label: "Ra", type: "NUMBER", nominal: "1.6", tol_plus: "0.2" },
    { key: "heat", label: "Heat", type: "TEXT" },
  ];
  it("auto-fills nominals when nothing was recorded", () => {
    const rows = qcRowsFromStep(fields, undefined);
    expect(rows[0]).toEqual({ parameter: "Bore", spec: "40.00 ± 0.02 mm", observed: "40.00", auto: true, result: "Pass" });
    expect(rows[1]!.spec).toBe("1.6 −0 / +0.2");
    expect(rows[2]).toMatchObject({ observed: "", auto: false, result: "" });
  });
});
