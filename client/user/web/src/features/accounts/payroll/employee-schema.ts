import { z } from "zod";
import type { Schemas } from "@/core/api/types";
import { add, isDecimal, sum } from "@/core/money";

const dec = z.string().trim().refine((v) => v === "" || isDecimal(v), "Enter a number");
const comp = z.object({ name: z.string().trim(), amount: dec });

export const employeeSchema = z.object({
  emp_code: z.string().trim().min(1, "Employee code is required"),
  full_name: z.string().trim().min(1, "Name is required"),
  department: z.string().trim(),
  designation: z.string().trim(),
  employee_category: z.enum(["SHOP_FLOOR_OPERATOR", "STAFF", "MANAGEMENT"]),
  date_of_joining: z.string().min(1, "Date of joining is required"),
  pan: z.string().trim().toUpperCase().refine((v) => v === "" || /^[A-Z]{5}\d{4}[A-Z]$/.test(v), "10-character PAN"),
  uan_epf: z.string().trim().refine((v) => v === "" || /^\d{12}$/.test(v), "12-digit UAN"),
  esic_ip_no: z.string().trim().refine((v) => v === "" || /^\d{10}$/.test(v), "10-digit IP number"),
  bank_account_no: z.string().trim(),
  bank_ifsc: z.string().trim().toUpperCase().refine((v) => v === "" || /^[A-Z]{4}0[A-Z0-9]{6}$/.test(v), "11-character IFSC"),
  tax_regime: z.enum(["NEW", "OLD"]),
  basic: dec.refine((v) => v !== "", "Basic is required"),
  da: dec, hra: dec, special: dec, conveyance: dec, piece_rate: dec, monthly_tds_override: dec,
  other_allowances: z.array(comp),
  other_deductions: z.array(comp),
  epf_applicable: z.boolean(), esic_applicable: z.boolean(), pt_applicable: z.boolean(),
});

export type EmployeeForm = z.input<typeof employeeSchema>;
export type EmployeeValues = z.output<typeof employeeSchema>;

export const emptyEmployee = (): EmployeeForm => ({
  emp_code: "", full_name: "", department: "", designation: "", employee_category: "STAFF", date_of_joining: "", pan: "", uan_epf: "", esic_ip_no: "",
  bank_account_no: "", bank_ifsc: "", tax_regime: "NEW", basic: "", da: "", hra: "", special: "", conveyance: "", piece_rate: "", monthly_tds_override: "",
  other_allowances: [], other_deductions: [], epf_applicable: true, esic_applicable: true, pt_applicable: true,
});

const n = (v: string) => v || null;
const comps = (l: { name: string; amount: string }[]) => l.filter((c) => c.name && c.amount).map((c) => ({ name: c.name, amount: c.amount }));

/** Fixed monthly earnings preview (basic + DA + HRA + special + conveyance + other allowances); statutory maths is server-side. */
export const monthlyGross = (v: Pick<EmployeeForm, "basic" | "da" | "hra" | "special" | "conveyance" | "other_allowances">) =>
  add(v.basic || "0", v.da || "0", v.hra || "0", v.special || "0", v.conveyance || "0", sum(v.other_allowances.map((a) => (a.name && isDecimal(a.amount) ? a.amount : "0"))));

export function toEmployeeIn(v: EmployeeValues): Schemas["EmployeeIn"] {
  return {
    emp_code: v.emp_code, full_name: v.full_name, department: n(v.department), designation: n(v.designation), employee_category: v.employee_category,
    date_of_joining: v.date_of_joining, pan: n(v.pan), uan_epf: n(v.uan_epf), esic_ip_no: n(v.esic_ip_no), bank_account_no: n(v.bank_account_no), bank_ifsc: n(v.bank_ifsc),
    tax_regime: v.tax_regime,
    salary_structure: {
      basic: v.basic, da: v.da || "0", hra: v.hra || "0", special: v.special || "0", conveyance: v.conveyance || "0",
      other_allowances: comps(v.other_allowances), other_deductions: comps(v.other_deductions),
      epf_applicable: v.epf_applicable, esic_applicable: v.esic_applicable, pt_applicable: v.pt_applicable,
      piece_rate: n(v.piece_rate), monthly_tds_override: n(v.monthly_tds_override),
    },
  };
}

export function fromEmployee(e: Schemas["EmployeeOut"]): EmployeeForm {
  const s = e.salary_structure;
  const z0 = (x: string | null | undefined) => (x && x !== "0" ? x : "");
  return {
    emp_code: e.emp_code, full_name: e.full_name, department: e.department ?? "", designation: e.designation ?? "",
    employee_category: (["SHOP_FLOOR_OPERATOR", "STAFF", "MANAGEMENT"].includes(e.employee_category) ? e.employee_category : "STAFF") as EmployeeForm["employee_category"],
    date_of_joining: e.date_of_joining, pan: e.pan ?? "", uan_epf: e.uan_epf ?? "", esic_ip_no: e.esic_ip_no ?? "", bank_account_no: e.bank_account_no ?? "", bank_ifsc: e.bank_ifsc ?? "",
    tax_regime: e.tax_regime === "OLD" ? "OLD" : "NEW", basic: s.basic, da: z0(s.da), hra: z0(s.hra), special: z0(s.special), conveyance: z0(s.conveyance),
    piece_rate: z0(s.piece_rate), monthly_tds_override: z0(s.monthly_tds_override), other_allowances: s.other_allowances ?? [], other_deductions: s.other_deductions ?? [],
    epf_applicable: s.epf_applicable, esic_applicable: s.esic_applicable, pt_applicable: s.pt_applicable,
  };
}
