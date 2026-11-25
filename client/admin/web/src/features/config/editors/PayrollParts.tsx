"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { isDecimalString } from "@/lib/money";
import type { IncomeTaxPayload, PtPayload, PtState, Regime } from "../schemas";
import { RowsTable } from "./RowsTable";
import { Section } from "./Section";

export function DecimalField({ label, value, onChange, readOnly, hint }: { label: string; value: string; onChange: (v: string) => void; readOnly: boolean; hint?: string }) {
  return (
    <Field label={label} hint={hint}>
      <Input inputMode="decimal" className="text-right tabular-nums" value={value} disabled={readOnly} aria-invalid={!isDecimalString(value)} onChange={(e) => onChange(e.target.value.replace(/[,\s₹%]/g, ""))} />
    </Field>
  );
}

function PtStateCard({ code, st, onChange, onRemove, readOnly }: { code: string; st: PtState; onChange: (s: PtState) => void; onRemove: () => void; readOnly: boolean }) {
  return (
    <div className="space-y-3 rounded-md border border-line p-3">
      <div className="flex flex-wrap items-end gap-3">
        <span className="rounded-sm bg-subtle px-2 py-1 font-mono text-xs text-ink-2">{code}</span>
        <Field label="State" className="w-48">
          <Input value={st.name} disabled={readOnly} onChange={(e) => onChange({ ...st, name: e.target.value })} />
        </Field>
        <Field label="Frequency" className="w-40">
          <NativeSelect value={st.frequency} disabled={readOnly} onChange={(e) => onChange({ ...st, frequency: e.target.value as PtState["frequency"] })}>
            <option value="MONTHLY">Monthly</option>
            <option value="HALF_YEARLY">Half-yearly</option>
            <option value="ANNUAL">Annual</option>
          </NativeSelect>
        </Field>
        {st.frequency !== "MONTHLY" ? (
          <Field label="Deduction months" hint="e.g. 9, 3" className="w-36">
            <Input
              value={(st.deduction_months ?? []).join(", ")}
              disabled={readOnly}
              onChange={(e) => onChange({ ...st, deduction_months: e.target.value.split(",").map((m) => Number.parseInt(m.trim(), 10)).filter((m) => m >= 1 && m <= 12) })}
            />
          </Field>
        ) : null}
        <Field label="Notes" className="min-w-48 flex-1">
          <Input value={st.notes ?? ""} disabled={readOnly} onChange={(e) => onChange({ ...st, notes: e.target.value })} />
        </Field>
        {!readOnly ? (
          <Button variant="ghost" size="icon" aria-label={`Remove ${st.name}`} onClick={onRemove}>
            <Trash2 />
          </Button>
        ) : null}
      </div>
      <RowsTable
        rows={st.slabs}
        readOnly={readOnly}
        onChange={(slabs) => onChange({ ...st, slabs: slabs as PtState["slabs"] })}
        addLabel="Add slab"
        newRow={() => ({ min: "0", max: null, amount: "0" })}
        columns={[
          { key: "min", label: "Gross from ₹", type: "decimal" },
          { key: "max", label: "Gross to ₹ (blank = above)", type: "decimalNullable" },
          { key: "amount", label: "PT ₹", type: "decimal", width: "120px" },
          { key: "feb_amount", label: "February ₹", type: "decimalNullable", width: "120px" },
        ]}
      />
    </div>
  );
}

export function PtStatesEditor({ value, onChange, readOnly }: { value: PtPayload; onChange: (v: PtPayload) => void; readOnly: boolean }) {
  const entries = Object.entries(value.states).sort(([a], [b]) => a.localeCompare(b));
  const setState = (code: string, st: PtState | null) => {
    const states = { ...value.states };
    if (st) states[code] = st;
    else delete states[code];
    onChange({ ...value, states });
  };
  const add = () => {
    const code = window.prompt("GST state code (2 digits), e.g. 33 for Tamil Nadu")?.trim();
    if (!code || !/^\d{2}$/.test(code) || value.states[code]) return;
    setState(code, { name: "", frequency: "MONTHLY", slabs: [] });
  };
  return (
    <Section title="Professional tax slabs per state" description="Gross salary ranges per deduction period, keyed by GST state code." actions={!readOnly ? <Button size="sm" onClick={add}><Plus /> Add state</Button> : null}>
      <div className="space-y-3">
        {entries.map(([code, st]) => (
          <PtStateCard key={code} code={code} st={st} readOnly={readOnly} onChange={(s) => setState(code, s)} onRemove={() => setState(code, null)} />
        ))}
      </div>
    </Section>
  );
}

function RegimeEditor({ title, regime, onChange, readOnly }: { title: string; regime: Regime; onChange: (r: Regime) => void; readOnly: boolean }) {
  const reb = regime.rebate_87a ?? { income_limit: "0", max_rebate: "0", marginal_relief: false };
  return (
    <div className="space-y-3 rounded-md border border-line p-3">
      <h4 className="text-[13px] font-semibold text-ink">{title}</h4>
      <div className="grid grid-cols-3 gap-3">
        <DecimalField label="Standard deduction ₹" value={regime.standard_deduction} readOnly={readOnly} onChange={(v) => onChange({ ...regime, standard_deduction: v })} />
        <DecimalField label="87A income limit ₹" value={reb.income_limit} readOnly={readOnly} onChange={(v) => onChange({ ...regime, rebate_87a: { ...reb, income_limit: v } })} />
        <DecimalField label="87A max rebate ₹" value={reb.max_rebate} readOnly={readOnly} onChange={(v) => onChange({ ...regime, rebate_87a: { ...reb, max_rebate: v } })} />
      </div>
      <label className="flex items-center gap-2 text-[13px] text-ink-2">
        <input type="checkbox" className="size-4 accent-[#C35E49]" checked={!!reb.marginal_relief} disabled={readOnly} onChange={(e) => onChange({ ...regime, rebate_87a: { ...reb, marginal_relief: e.target.checked } })} />
        Marginal relief on 87A rebate
      </label>
      <RowsTable
        rows={regime.slabs}
        readOnly={readOnly}
        onChange={(slabs) => onChange({ ...regime, slabs: slabs as Regime["slabs"] })}
        addLabel="Add slab"
        newRow={() => ({ from: "0", to: null, rate: "0" })}
        columns={[
          { key: "from", label: "Income from ₹", type: "decimal" },
          { key: "to", label: "Income to ₹", type: "decimalNullable" },
          { key: "rate", label: "Rate %", type: "decimal", width: "100px" },
        ]}
      />
      <RowsTable
        rows={regime.surcharge ?? []}
        readOnly={readOnly}
        onChange={(surcharge) => onChange({ ...regime, surcharge: surcharge as Regime["surcharge"] })}
        addLabel="Add surcharge band"
        newRow={() => ({ above: "0", rate: "0" })}
        columns={[
          { key: "above", label: "Surcharge above ₹", type: "decimal" },
          { key: "rate", label: "Surcharge %", type: "decimal", width: "110px" },
        ]}
      />
    </div>
  );
}

const REGIME_LABEL: Record<string, string> = { NEW: "New regime (default)", OLD: "Old regime" };

export function IncomeTaxFields({ value, onChange, readOnly }: { value: IncomeTaxPayload; onChange: (v: IncomeTaxPayload) => void; readOnly: boolean }) {
  return (
    <Section title="Income-tax slabs (Sec 192)" description="Annual taxable income slabs per regime; health & education cess applies on tax + surcharge.">
      <div className="grid max-w-md grid-cols-2 gap-3">
        <Field label="Financial year">
          <Input value={value.fy ?? ""} disabled={readOnly} onChange={(e) => onChange({ ...value, fy: e.target.value })} placeholder="2025-26" />
        </Field>
        <DecimalField label="Cess %" value={value.cess_rate} readOnly={readOnly} onChange={(cess_rate) => onChange({ ...value, cess_rate })} />
      </div>
      <div className="grid gap-4 2xl:grid-cols-2">
        {Object.entries(value.regimes).map(([k, r]) => (
          <RegimeEditor key={k} title={REGIME_LABEL[k] ?? k} regime={r} readOnly={readOnly} onChange={(nr) => onChange({ ...value, regimes: { ...value.regimes, [k]: nr } })} />
        ))}
      </div>
    </Section>
  );
}
