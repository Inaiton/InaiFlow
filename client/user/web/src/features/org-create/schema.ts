import { z } from "zod";
import { fyForDate, todayIso } from "@/core/dates";

export const GSTIN_RE = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
export const PAN_RE = /^[A-Z]{5}\d{4}[A-Z]$/;
export const TAN_RE = /^[A-Z]{4}\d{5}[A-Z]$/;
export const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$/;

export const GST_REG_TYPES = [
  { value: "REGULAR", label: "Regular" },
  { value: "COMPOSITION", label: "Composition" },
  { value: "UNREGISTERED", label: "Unregistered" },
  { value: "SEZ", label: "SEZ" },
];

export const INDUSTRIES = [
  { value: "PRECISION_MACHINING", label: "Precision machining" },
  { value: "FABRICATION", label: "Fabrication & welding" },
  { value: "CASTING_FORGING", label: "Casting & forging" },
  { value: "ELECTRICAL", label: "Electrical & electronics" },
  { value: "PLASTICS", label: "Plastics & moulding" },
  { value: "TEXTILES", label: "Textiles" },
  { value: "FOOD", label: "Food processing" },
  { value: "SERVICES", label: "Engineering services" },
  { value: "OTHER", label: "Other manufacturing" },
];

const opt = (re: RegExp, msg: string) =>
  z.string().trim().toUpperCase().refine((v) => v === "" || re.test(v), msg);

export const orgCreateSchema = z
  .object({
    legal_name: z.string().trim().min(2, "Enter the company’s legal name").max(200),
    mailing_name: z.string().trim().max(200),
    address_line1: z.string().trim().min(3, "Enter the registered address").max(200),
    address_line2: z.string().trim().max(200),
    city: z.string().trim().min(2, "Enter the city").max(80),
    state_code: z.string().min(1, "Pick a state"),
    pincode: z.string().trim().regex(/^\d{6}$/, "6-digit PIN code"),
    contact_email: z.email("Enter a valid email").trim(),
    contact_phone: z.string().trim().regex(/^[+\d][\d\s-]{6,18}$/, "Enter a valid phone number"),
    gst_reg_type: z.string().min(1),
    gstin: opt(GSTIN_RE, "GSTIN looks like 33AAKCA4821M1Z6"),
    pan: opt(PAN_RE, "PAN looks like AAKCA4821M"),
    tan: opt(TAN_RE, "TAN looks like CHEA12345B"),
    cin_or_udyam: z.string().trim().max(30),
    epf_code: z.string().trim().max(30),
    esic_code: z.string().trim().max(30),
    fy_begins_from: z.iso.date("Pick a date"),
    books_beginning_from: z.iso.date("Pick a date"),
    workspace_slug: z.string().trim().toLowerCase().regex(SLUG_RE, "3–40 lowercase letters, digits or hyphens"),
    industry_type: z.string().min(1, "Pick an industry"),
    iso_standard: z.string().trim().max(40),
  })
  .refine((v) => v.gst_reg_type === "UNREGISTERED" || v.gstin !== "", { path: ["gstin"], message: "GSTIN is required for registered businesses" })
  .refine((v) => v.gstin === "" || !/^\d{2}$/.test(v.state_code) || v.gstin.startsWith(v.state_code), {
    path: ["gstin"],
    message: "GSTIN state code doesn’t match the selected state",
  })
  .refine((v) => v.books_beginning_from >= v.fy_begins_from, { path: ["books_beginning_from"], message: "Books can’t begin before the financial year" });

export type OrgCreateValues = z.input<typeof orgCreateSchema>;
export type OrgCreateOutput = z.output<typeof orgCreateSchema>;

export const STEP_FIELDS: (keyof OrgCreateValues)[][] = [
  ["legal_name", "mailing_name", "address_line1", "address_line2", "city", "state_code", "pincode", "contact_email", "contact_phone"],
  ["gst_reg_type", "gstin", "pan", "tan", "cin_or_udyam", "epf_code", "esic_code"],
  ["fy_begins_from", "books_beginning_from", "workspace_slug", "industry_type", "iso_standard"],
  [],
];

export function defaultOrgValues(): OrgCreateValues {
  const fy = fyForDate(todayIso());
  return {
    legal_name: "", mailing_name: "", address_line1: "", address_line2: "", city: "", state_code: "", pincode: "",
    contact_email: "", contact_phone: "", gst_reg_type: "REGULAR", gstin: "", pan: "", tan: "", cin_or_udyam: "",
    epf_code: "", esic_code: "", fy_begins_from: fy.start, books_beginning_from: fy.start, workspace_slug: "",
    industry_type: "PRECISION_MACHINING", iso_standard: "ISO 9001:2015",
  };
}

/** "Arul Precision Components Pvt Ltd" → "arul-precision-components" */
export function suggestSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/\b(private|pvt|limited|ltd|llp|inc|co)\b\.?/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40)
    .replace(/-+$/g, "");
}

/** PAN is characters 3–12 of a GSTIN. */
export const panFromGstin = (gstin: string): string => (GSTIN_RE.test(gstin) ? gstin.slice(2, 12) : "");

const nullable = (s: string) => (s === "" ? null : s);

export function toOrgCreateIn(v: OrgCreateOutput) {
  return {
    legal_name: v.legal_name, mailing_name: nullable(v.mailing_name), workspace_slug: v.workspace_slug,
    address_line1: v.address_line1, address_line2: nullable(v.address_line2), city: v.city, state_code: v.state_code,
    pincode: v.pincode, country: "India", fy_begins_from: v.fy_begins_from, books_beginning_from: v.books_beginning_from,
    contact_email: v.contact_email, contact_phone: v.contact_phone, gst_reg_type: v.gst_reg_type, gstin: nullable(v.gstin),
    pan: nullable(v.pan), tan: nullable(v.tan), cin_or_udyam: nullable(v.cin_or_udyam), epf_code: nullable(v.epf_code),
    esic_code: nullable(v.esic_code), industry_type: v.industry_type, iso_standard: nullable(v.iso_standard),
  };
}
