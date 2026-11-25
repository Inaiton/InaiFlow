import { describe, expect, it } from "vitest";
import { emptyEmployee, employeeSchema, monthlyGross, toEmployeeIn } from "./employee-schema";

describe("employee schema", () => {
  it("previews gross and maps the salary structure", () => {
    const f = { ...emptyEmployee(), emp_code: "E1", full_name: "Murugan K", date_of_joining: "2026-04-01", basic: "12000", hra: "4800", other_allowances: [{ name: "Shift", amount: "500" }, { name: "", amount: "9" }] };
    expect(monthlyGross(f)).toBe("17300");
    const body = toEmployeeIn(employeeSchema.parse(f));
    expect(body.salary_structure.other_allowances).toEqual([{ name: "Shift", amount: "500" }]);
    expect(body.salary_structure.da).toBe("0");
    expect(body.pan).toBeNull();
  });
  it("validates UAN and IFSC", () => {
    expect(employeeSchema.safeParse({ ...emptyEmployee(), emp_code: "E", full_name: "X", date_of_joining: "2026-04-01", basic: "1", uan_epf: "123" }).success).toBe(false);
  });
});
