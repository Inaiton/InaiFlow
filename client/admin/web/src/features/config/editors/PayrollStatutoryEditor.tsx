"use client";

import { Field, Input } from "@/components/ui/input";
import { lenient, payrollPart, type EpfPayload, type EsicPayload } from "../schemas";
import { JsonEditor } from "./JsonEditor";
import { DecimalField, IncomeTaxFields, PtStatesEditor } from "./PayrollParts";
import { Section } from "./Section";
import type { EditorProps } from "./types";

const EPF_FIELDS = [
  ["wage_ceiling", "EPF wage ceiling ₹/month"],
  ["employee_rate", "Employee share %"],
  ["employer_epf_rate", "Employer EPF %"],
  ["employer_eps_rate", "Employer EPS %"],
  ["employer_eps_cap", "EPS cap ₹/month"],
  ["edli_rate", "EDLI %"],
  ["edli_cap", "EDLI cap ₹/month"],
  ["admin_charges_rate", "Admin charges %"],
  ["admin_charges_min", "Admin charges min ₹"],
] as const;

const ESIC_FIELDS = [
  ["gross_ceiling", "Gross wage ceiling ₹"],
  ["gross_ceiling_disabled", "Ceiling (persons with disability) ₹"],
  ["employee_rate", "Employee share %"],
  ["employer_rate", "Employer share %"],
] as const;

function EpfEditor({ v, onChange, ro }: { v: EpfPayload; onChange: (v: EpfPayload) => void; ro: boolean }) {
  return (
    <Section title="EPF" description="Employees' Provident Fund: wages = Basic + DA up to the ceiling.">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {EPF_FIELDS.map(([k, label]) => (
          <DecimalField key={k} label={label} value={v[k] ?? ""} readOnly={ro} onChange={(x) => onChange({ ...v, [k]: x })} />
        ))}
        <Field label="Mandatory from (employees)">
          <Input inputMode="numeric" value={String(v.mandatory_employee_count ?? "")} disabled={ro} onChange={(e) => onChange({ ...v, mandatory_employee_count: Number.parseInt(e.target.value || "0", 10) || 0 })} />
        </Field>
      </div>
    </Section>
  );
}

function EsicEditor({ v, onChange, ro }: { v: EsicPayload; onChange: (v: EsicPayload) => void; ro: boolean }) {
  return (
    <Section title="ESIC" description="Applies when gross monthly wages are within the ceiling; employee share rounds up to the next rupee.">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {ESIC_FIELDS.map(([k, label]) => (
          <DecimalField key={k} label={label} value={v[k] ?? ""} readOnly={ro} onChange={(x) => onChange({ ...v, [k]: x })} />
        ))}
      </div>
    </Section>
  );
}

/** PAYROLL_STATUTORY: one config per key (EPF, ESIC, PT_SLABS, INCOME_TAX); the part is detected from the payload. */
export function PayrollStatutoryEditor(props: EditorProps) {
  const ro = props.readOnly;
  switch (payrollPart(props.value)) {
    case "EPF":
      return <EpfEditor v={lenient.epf.parse(props.value)} ro={ro} onChange={props.onChange} />;
    case "ESIC":
      return <EsicEditor v={lenient.esic.parse(props.value)} ro={ro} onChange={props.onChange} />;
    case "PT":
      return <PtStatesEditor value={lenient.pt.parse(props.value)} readOnly={ro} onChange={props.onChange} />;
    case "IT":
      return <IncomeTaxFields value={lenient.incomeTax.parse(props.value)} readOnly={ro} onChange={props.onChange} />;
    default:
      return <JsonEditor {...props} notice="Payload is not a recognised payroll statutory part (EPF, ESIC, PT slabs or income tax); editing as JSON." />;
  }
}
