"use client";

import { Field, Input } from "@/components/ui/input";
import { lenient, type TdsPayload } from "../schemas";
import { JsonEditor } from "./JsonEditor";
import { RowsTable } from "./RowsTable";
import { Section } from "./Section";
import type { EditorProps } from "./types";

export function TdsSectionsEditor(props: EditorProps) {
  const parsed = lenient.tds.safeParse(props.value);
  if (!parsed.success) return <JsonEditor {...props} notice="Payload does not match the TDS/TCS shape ({ sections }); editing as JSON." />;
  const v: TdsPayload = parsed.data;
  const ro = props.readOnly;
  return (
    <div className="space-y-6">
      <Section title="Deposit due dates" description="ITNS 281 challan due date for deductions of a month.">
        <div className="grid max-w-md grid-cols-2 gap-3">
          <Field label="Day of next month">
            <Input inputMode="numeric" value={String(v.due_day_of_next_month ?? "")} disabled={ro} onChange={(e) => props.onChange({ ...v, due_day_of_next_month: Number.parseInt(e.target.value, 10) || 0 })} />
          </Field>
          <Field label="March deductions due (MM-DD)">
            <Input value={v.march_due_date ?? ""} disabled={ro} onChange={(e) => props.onChange({ ...v, march_due_date: e.target.value })} placeholder="04-30" />
          </Field>
        </div>
      </Section>
      <Section title="TDS / TCS sections" description="Thresholds in ₹ (blank = none). Rates in %. No-PAN rate applies under Sec 206AA / 206CC. 'On excess' = rate applies only above the annual threshold.">
        <RowsTable
          rows={v.sections}
          readOnly={ro}
          onChange={(sections) => props.onChange({ ...v, sections })}
          addLabel="Add section"
          newRow={() => ({ kind: "TDS", section: "", nature: "", threshold_single: null, threshold_annual: null, rate_individual: "", rate_company: "", rate_no_pan: "20" })}
          columns={[
            { key: "section", label: "Section", type: "text", mono: true, width: "100px" },
            { key: "kind", label: "Kind", type: "select", options: ["TDS", "TCS"], width: "90px" },
            { key: "nature", label: "Nature of payment", type: "text" },
            { key: "threshold_single", label: "Single ₹", type: "decimalNullable", width: "115px" },
            { key: "threshold_annual", label: "Annual ₹", type: "decimalNullable", width: "115px" },
            { key: "applies_on_excess", label: "On excess", type: "bool", width: "80px" },
            { key: "rate_individual", label: "Indiv/HUF %", type: "decimal", width: "95px" },
            { key: "rate_company", label: "Company %", type: "decimal", width: "95px" },
            { key: "rate_no_pan", label: "No PAN %", type: "decimal", width: "95px" },
          ]}
        />
      </Section>
    </div>
  );
}
