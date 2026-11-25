import { z } from "zod";

export const MODULE_FLAGS = [
  ["accounts", "Accounts"],
  ["payroll", "Payroll"],
  ["operations", "Operations"],
  ["documents", "Documents"],
  ["tally_xml_sync", "Tally XML sync"],
  ["irp_einvoice", "IRP e-Invoice"],
] as const;

const money = z.string().regex(/^\d+(\.\d{1,4})?$/, "Amount like 4999 or 4999.50");
const count = z.number({ message: "Required" }).int().min(0);

export const planFormSchema = z.object({
  plan_code: z.string().regex(/^[A-Z0-9_]{2,40}$/, "UPPER_SNAKE_CASE, 2–40 chars"),
  name: z.string().min(2),
  monthly_price_inr: money,
  annual_price_inr: money,
  max_internal_seats: count,
  max_external_collaborators: count,
  max_storage_gb: count,
  enabled_modules: z.record(z.string(), z.boolean()),
  is_active: z.boolean(),
  reason: z.string().trim().min(5, "At least 5 characters (recorded in platform audit)"),
});
export type PlanFormValues = z.infer<typeof planFormSchema>;
