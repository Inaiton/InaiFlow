"use client";

import { Field, Input } from "@/components/ui/input";
import { lenient, type GstPayload } from "../schemas";
import { JsonEditor } from "./JsonEditor";
import { DecimalField } from "./PayrollParts";
import { RowsTable } from "./RowsTable";
import { Section } from "./Section";
import type { EditorProps } from "./types";

export function GstSlabsEditor(props: EditorProps) {
  const parsed = lenient.gst.safeParse(props.value);
  if (!parsed.success) return <JsonEditor {...props} notice="Payload does not match the GST shape ({ rates, cess, thresholds, rcm_common }); editing as JSON." />;
  const v: GstPayload = parsed.data;
  const ro = props.readOnly;
  const set = (patch: Partial<GstPayload>) => props.onChange({ ...v, ...patch });
  const thr = (k: "eway_bill_threshold" | "einvoice_aato_threshold" | "b2cl_threshold", label: string, hint: string) => (
    <DecimalField label={label} hint={hint} value={v[k] ?? ""} readOnly={ro} onChange={(x) => set({ [k]: x })} />
  );
  return (
    <div className="space-y-6">
      <Section title="GST rate slabs" description="Rates as percentages. Verify against the latest CBIC notification before publishing.">
        <div className="max-w-sm">
          <RowsTable
            rows={v.rates.map((rate) => ({ rate }))}
            readOnly={ro}
            onChange={(rows) => set({ rates: rows.map((r) => String(r.rate ?? "")) })}
            newRow={() => ({ rate: "" })}
            addLabel="Add slab"
            columns={[{ key: "rate", label: "Rate %", type: "decimal" }]}
          />
        </div>
      </Section>
      <Section title="Cess" description="Supported cess modes: ad-valorem % and/or specific ₹ per unit (rates are set per stock item).">
        <Field label="Modes (comma separated)" className="max-w-md">
          <Input
            className="font-mono text-[13px]"
            value={(v.cess?.modes ?? []).join(", ")}
            disabled={ro}
            onChange={(e) => set({ cess: { ...v.cess, modes: e.target.value.split(",").map((m) => m.trim()).filter(Boolean) } })}
          />
        </Field>
      </Section>
      <Section title="Thresholds">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          {thr("eway_bill_threshold", "e-Way bill consignment ₹", "Default inter-state threshold")}
          {thr("einvoice_aato_threshold", "e-Invoice AATO ₹", "Aggregate annual turnover")}
          {thr("b2cl_threshold", "B2C Large invoice ₹", "GSTR-1 table 5A")}
          <Field label="HSN digits (turnover ≤ ₹5 Cr)">
            <Input inputMode="numeric" value={String(v.hsn_digits?.upto_5cr ?? "")} disabled={ro} onChange={(e) => set({ hsn_digits: { upto_5cr: Number(e.target.value) || 0, above_5cr: v.hsn_digits?.above_5cr ?? 6 } })} />
          </Field>
          <Field label="HSN digits (turnover > ₹5 Cr)">
            <Input inputMode="numeric" value={String(v.hsn_digits?.above_5cr ?? "")} disabled={ro} onChange={(e) => set({ hsn_digits: { upto_5cr: v.hsn_digits?.upto_5cr ?? 4, above_5cr: Number(e.target.value) || 0 } })} />
          </Field>
        </div>
      </Section>
      <Section title="Common reverse-charge (RCM) services">
        <RowsTable
          rows={v.rcm_common ?? []}
          readOnly={ro}
          onChange={(rcm_common) => set({ rcm_common: rcm_common as GstPayload["rcm_common"] })}
          newRow={() => ({ service: "", rate: "" })}
          addLabel="Add service"
          columns={[
            { key: "service", label: "Service", type: "text" },
            { key: "rate", label: "Rate %", type: "decimal", width: "140px" },
          ]}
        />
      </Section>
    </div>
  );
}
