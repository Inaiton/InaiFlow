import { z } from "zod";
import { isDecimal } from "@/core/money";
import type { Schemas } from "@/core/api/types";

const optDec = z.string().trim().refine((v) => v === "" || isDecimal(v), "Enter a number");
const optInt = z.string().trim().refine((v) => v === "" || /^\d+$/.test(v), "Whole days");
export const GSTIN_RE = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
const PAN_RE = /^[A-Z]{5}\d{4}[A-Z]$/;
const IFSC_RE = /^[A-Z]{4}0[A-Z0-9]{6}$/;

export const ledgerSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  alias: z.string().trim(),
  group_id: z.string().min(1, "Choose a group"),
  opening_balance: optDec,
  opening_balance_type: z.enum(["DR", "CR"]),
  maintain_bill_by_bill: z.boolean(),
  default_credit_days: optInt,
  credit_limit: optDec,
  is_active: z.boolean(),
  gstin: z.string().trim().toUpperCase().refine((v) => v === "" || GSTIN_RE.test(v), "15-character GSTIN, e.g. 33AAKCA4821M1Z6"),
  state_code: z.string(),
  pan: z.string().trim().toUpperCase().refine((v) => v === "" || PAN_RE.test(v), "10-character PAN"),
  msme_type: z.string(),
  udyam_no: z.string().trim(),
  address: z.string().trim(),
  email: z.string().trim().refine((v) => v === "" || /^\S+@\S+\.\S+$/.test(v), "Enter a valid email"),
  phone: z.string().trim(),
  bank_account: z.string().trim(),
  ifsc: z.string().trim().toUpperCase().refine((v) => v === "" || IFSC_RE.test(v), "11-character IFSC"),
  is_sez: z.boolean(),
  is_unregistered: z.boolean(),
  deductee_type: z.string(),
  tax_type: z.string(),
  gst_head: z.string(),
  tax_rate: optDec,
  tds_section: z.string(),
  interest_rate: optDec,
  interest_basis: z.string(),
  grace_days: optInt,
});

export type LedgerForm = z.input<typeof ledgerSchema>;
export type LedgerValues = z.output<typeof ledgerSchema>;

export const emptyLedger = (groupId = ""): LedgerForm => ({
  name: "", alias: "", group_id: groupId, opening_balance: "", opening_balance_type: "DR", maintain_bill_by_bill: false,
  default_credit_days: "", credit_limit: "", is_active: true, gstin: "", state_code: "", pan: "", msme_type: "", udyam_no: "",
  address: "", email: "", phone: "", bank_account: "", ifsc: "", is_sez: false, is_unregistered: false, deductee_type: "",
  tax_type: "", gst_head: "", tax_rate: "", tds_section: "", interest_rate: "", interest_basis: "PAST_DUE", grace_days: "",
});

const n = (v: string) => (v === "" ? null : v);

/** Form values → LedgerIn. Party/tax/interest blocks are sent only when something is filled. */
export function toLedgerIn(v: LedgerValues, cls: "party" | "bank" | "tax" | "cash" | "other"): Schemas["LedgerIn"] {
  const party: Schemas["PartyDetails"] = {
    gstin: n(v.gstin), state_code: n(v.state_code), pan: n(v.pan), msme_type: n(v.msme_type), udyam_no: n(v.udyam_no), address: n(v.address),
    email: n(v.email), phone: n(v.phone), bank_account: n(v.bank_account), ifsc: n(v.ifsc), is_sez: v.is_sez, is_unregistered: v.is_unregistered,
    deductee_type: n(v.deductee_type),
  };
  const hasParty = cls === "party" || cls === "bank" || Object.entries(party).some(([, x]) => x !== null && x !== false);
  return {
    name: v.name,
    alias: n(v.alias),
    group_id: v.group_id,
    opening_balance: v.opening_balance || "0",
    opening_balance_type: v.opening_balance_type,
    maintain_bill_by_bill: v.maintain_bill_by_bill,
    default_credit_days: v.default_credit_days === "" ? null : Number(v.default_credit_days),
    credit_limit: n(v.credit_limit),
    is_active: v.is_active,
    party_details: hasParty ? party : null,
    tax_config: v.tax_type ? { tax_type: v.tax_type, gst_head: n(v.gst_head), rate: n(v.tax_rate), tds_section: n(v.tds_section) } : null,
    interest_config: v.interest_rate ? { rate_pct: v.interest_rate, basis: v.interest_basis || "PAST_DUE", grace_days: v.grace_days === "" ? 0 : Number(v.grace_days) } : null,
  };
}

/** LedgerOut → form values for editing. */
export function fromLedger(l: Schemas["LedgerOut"]): LedgerForm {
  const p = l.party_details ?? {};
  return {
    ...emptyLedger(l.group_id),
    name: l.name, alias: l.alias ?? "", opening_balance: l.opening_balance === "0" ? "" : l.opening_balance, opening_balance_type: l.opening_balance_type,
    maintain_bill_by_bill: l.maintain_bill_by_bill, default_credit_days: l.default_credit_days?.toString() ?? "", credit_limit: l.credit_limit ?? "",
    is_active: l.is_active, gstin: p.gstin ?? "", state_code: p.state_code ?? "", pan: p.pan ?? "", msme_type: p.msme_type ?? "",
    udyam_no: p.udyam_no ?? "", address: p.address ?? "", email: p.email ?? "", phone: p.phone ?? "", bank_account: p.bank_account ?? "",
    ifsc: p.ifsc ?? "", is_sez: p.is_sez ?? false, is_unregistered: p.is_unregistered ?? false, deductee_type: p.deductee_type ?? "",
    tax_type: l.tax_config?.tax_type ?? "", gst_head: l.tax_config?.gst_head ?? "", tax_rate: l.tax_config?.rate ?? "", tds_section: l.tax_config?.tds_section ?? "",
    interest_rate: l.interest_config?.rate_pct ?? "", interest_basis: l.interest_config?.basis ?? "PAST_DUE", grace_days: l.interest_config?.grace_days?.toString() ?? "",
  };
}

/** GSTIN → { state_code, pan } (first two digits, chars 3–12). */
export function partsFromGstin(gstin: string): { state_code: string; pan: string } | null {
  const g = gstin.trim().toUpperCase();
  return GSTIN_RE.test(g) ? { state_code: g.slice(0, 2), pan: g.slice(2, 12) } : null;
}
