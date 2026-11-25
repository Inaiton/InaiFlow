import { z } from "zod";

/**
 * Payload shapes for structured config editors (contract types `payload: json`).
 * `lenient` decides whether a structured editor can render a payload (decimals = any string);
 * `strict` validates before save (decimals must match the contract decimal pattern).
 * Objects are loose so unknown keys written by the server are preserved.
 */
const DEC = /^-?\d+(\.\d{1,4})?$/;

export function makeSchemas(strict: boolean) {
  const dec = strict ? z.string().regex(DEC, "Must be a decimal like 18 or 0.75") : z.string();
  const decN = dec.nullable();

  // server/app/seeds/tax_rules.py GST_SLABS
  const gst = z.looseObject({
    rates: z.array(dec),
    cess: z.looseObject({ modes: z.array(z.string()) }).optional(),
    eway_bill_threshold: dec.optional(),
    einvoice_aato_threshold: dec.optional(),
    b2cl_threshold: dec.optional(),
    hsn_digits: z.looseObject({ upto_5cr: z.number().int(), above_5cr: z.number().int() }).optional(),
    rcm_common: z.array(z.looseObject({ service: z.string(), rate: dec })).optional(),
  });

  const tds = z.looseObject({
    due_day_of_next_month: z.number().int().optional(),
    march_due_date: z.string().optional(),
    sections: z.array(
      z.looseObject({
        section: z.string().min(1),
        nature: z.string(),
        kind: z.enum(["TDS", "TCS"]).optional(),
        threshold_single: decN,
        threshold_annual: decN,
        applies_on_excess: z.boolean().optional(),
        rate_individual: dec,
        rate_company: dec,
        rate_no_pan: dec,
      }),
    ),
  });

  const epf = z.looseObject({
    wage_ceiling: dec,
    employee_rate: dec,
    employer_eps_rate: dec,
    employer_eps_cap: dec,
    employer_epf_rate: dec,
    edli_rate: dec,
    edli_cap: dec.optional(),
    admin_charges_rate: dec,
    admin_charges_min: dec,
    mandatory_employee_count: z.number().int().optional(),
  });
  const esic = z.looseObject({ gross_ceiling: dec, gross_ceiling_disabled: dec.optional(), employee_rate: dec, employer_rate: dec });

  const ptSlab = z.looseObject({ min: dec, max: decN, amount: dec, feb_amount: decN.optional() });
  const ptState = z.looseObject({
    name: z.string(),
    frequency: z.enum(["MONTHLY", "HALF_YEARLY", "ANNUAL"]),
    deduction_months: z.array(z.number().int().min(1).max(12)).optional(),
    slabs: z.array(ptSlab),
    notes: z.string().optional(),
  });
  const pt = z.looseObject({ states: z.record(z.string(), ptState) });

  const regime = z.looseObject({
    standard_deduction: dec,
    slabs: z.array(z.looseObject({ from: dec, to: decN, rate: dec })),
    rebate_87a: z.looseObject({ income_limit: dec, max_rebate: dec, marginal_relief: z.boolean().optional() }).optional(),
    surcharge: z.array(z.looseObject({ above: dec, rate: dec })).optional(),
  });
  const incomeTax = z.looseObject({ fy: z.string().optional(), cess_rate: dec, regimes: z.record(z.string(), regime) });

  return { gst, tds, epf, esic, ptState, pt, regime, incomeTax };
}

export const lenient = makeSchemas(false);
export const strict = makeSchemas(true);

export type GstPayload = z.infer<typeof lenient.gst>;
export type TdsPayload = z.infer<typeof lenient.tds>;
export type EpfPayload = z.infer<typeof lenient.epf>;
export type EsicPayload = z.infer<typeof lenient.esic>;
export type PtState = z.infer<typeof lenient.ptState>;
export type PtPayload = z.infer<typeof lenient.pt>;
export type Regime = z.infer<typeof lenient.regime>;
export type IncomeTaxPayload = z.infer<typeof lenient.incomeTax>;

/** PAYROLL_STATUTORY holds several keys (EPF, ESIC, PT_SLABS, INCOME_TAX); detect the part by payload shape. */
export function payrollPart(v: unknown): "EPF" | "ESIC" | "PT" | "IT" | null {
  if (lenient.pt.safeParse(v).success) return "PT";
  if (lenient.incomeTax.safeParse(v).success) return "IT";
  if (lenient.epf.safeParse(v).success) return "EPF";
  if (lenient.esic.safeParse(v).success) return "ESIC";
  return null;
}

export const LEVELS = ["NONE", "READ", "WRITE", "FULL"] as const;
export const levelSchema = z.enum(LEVELS);
const role = z.looseObject({
  role_code: z.string().optional(),
  role_name: z.string().optional(),
  is_external_collaborator: z.boolean().optional(),
  permissions: z.record(z.string(), levelSchema),
});
export const rolesSchema = z.union([z.looseObject({ roles: z.array(role) }), role]);
export type RoleBlueprint = z.infer<typeof role>;

export interface FolderNode {
  name: string;
  children?: FolderNode[];
  [k: string]: unknown;
}
const folderNode: z.ZodType<FolderNode> = z.lazy(() => z.looseObject({ name: z.string(), children: z.array(folderNode).optional() }));
export const folderNodeSchema = folderNode;
export const folderListSchema = z.array(folderNode);

export function firstIssue(err: z.ZodError): string {
  const i = err.issues[0];
  return i ? `${i.path.join(".") || "(root)"}: ${i.message}` : "Invalid payload";
}
