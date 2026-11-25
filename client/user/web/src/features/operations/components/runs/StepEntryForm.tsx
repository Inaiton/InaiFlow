"use client";

import { CheckCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AdvancedSection, Button, DecimalInput, Field, Hint, NativeSelect, Segmented, Textarea } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { formatQty } from "@/core/money";
import { useCan } from "@/core/permissions/Can";
import { useInstruments } from "../../api/iso";
import { useExecuteStep } from "../../api/runs";
import type { WorkflowNode } from "../../lib/graph";
import { acceptRemainder, checkCounts, type StepCounts } from "../../lib/quantities";
import { countOutOfTolerance, missingRequired, quickQcAutofill } from "../../lib/tolerance";
import { QcReadingsTable } from "./QcReadingsTable";

export type EntryMode = "full" | "quick";

/** Step entry (design Ops-Run-StepEntry / Run-QuickQC). Used in the dialog and the shop-floor view. */
export function StepEntryForm({ runId, step, node, initialMode, onDone, onCancel }: {
  runId: string; step: Schemas["StepOut"]; node: WorkflowNode | undefined; initialMode: EntryMode;
  onDone: (out: Schemas["StepExecuteOut"]) => void; onCancel?: () => void;
}) {
  const fields = useMemo(() => node?.config.qc_fields ?? [], [node]);
  const canIso = useCan("operations.iso_compliance", "READ");
  const instruments = useInstruments(undefined, canIso);
  const execute = useExecuteStep(runId);
  const [key] = useState(() => crypto.randomUUID());
  const [mode, setMode] = useState<EntryMode>(initialMode);
  const [counts, setCounts] = useState<StepCounts>(() => ({ input: step.input_qty, accepted: initialMode === "quick" ? step.input_qty : "", rejected: initialMode === "quick" ? "0" : "", rework: "" }));
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const [k, r] of Object.entries(step.qc_measurements ?? {})) if (r.value && !r.auto_filled) init[k] = r.value;
    return initialMode === "quick" ? Object.fromEntries(Object.entries(quickQcAutofill(fields, init)).map(([k, r]) => [k, r.value])) : init;
  });
  const [auto, setAuto] = useState<Set<string>>(() => (initialMode === "quick" ? new Set(fields.filter((f) => f.nominal && !values[f.key]).map((f) => f.key)) : new Set()));
  const [instrumentId, setInstrumentId] = useState(step.instrument_id ?? "");
  const [defect, setDefect] = useState("");
  const [notes, setNotes] = useState("");
  const [override, setOverride] = useState("");
  const [error, setError] = useState<string | null>(null);

  const check = checkCounts(counts);
  const quick = mode === "quick";
  const missing = missingRequired(fields, values, quick);
  const out = countOutOfTolerance(fields, values);
  const needInstrument = Boolean(node?.config.instrument_required) && canIso && !instrumentId;
  const ready = check.ok && missing.length === 0 && !needInstrument && (!check.needsDefect || defect.trim().length > 0) && (!step.is_locked || override.trim().length >= 3);

  const switchMode = (m: EntryMode) => {
    setMode(m);
    if (m === "quick") {
      const entered = Object.fromEntries(Object.entries(values).filter(([k]) => !auto.has(k)));
      const filled = quickQcAutofill(fields, entered);
      setValues(Object.fromEntries(Object.entries(filled).map(([k, r]) => [k, r.value])));
      setAuto(new Set(Object.entries(filled).filter(([, r]) => r.autoFilled).map(([k]) => k)));
    } else {
      setValues((v) => Object.fromEntries(Object.entries(v).filter(([k]) => !auto.has(k))));
      setAuto(new Set());
    }
  };
  const setReading = (k: string, v: string) => {
    setValues((s) => ({ ...s, [k]: v }));
    setAuto((a) => { const n = new Set(a); n.delete(k); return n; });
  };
  const setCount = (f: keyof StepCounts) => (v: string | null) => setCounts((c) => ({ ...c, [f]: v ?? "" }));

  const submit = async () => {
    setError(null);
    const measurements = Object.fromEntries(Object.entries(values).filter(([k, v]) => v.trim() !== "" && !auto.has(k)));
    try {
      const res = await execute.mutateAsync({ stepId: step.id, key, body: {
        input_qty: counts.input, accepted_qty: counts.accepted || "0", rejected_qty: counts.rejected || "0", rework_qty: counts.rework || "0",
        measurements, quick_qc: quick, instrument_id: instrumentId || null, notes: notes.trim() || null,
        defect_description: check.needsDefect ? defect.trim() : null, override_reason: step.is_locked ? override.trim() : null,
      } });
      const bits = [`${formatQty(res.step.accepted_qty)} accepted`];
      if (res.ncr) bits.push(`${res.ncr.ncr_number} raised`);
      if (res.stock_voucher_id) bits.push("stock moved in Accounts");
      toast.success(`${res.step.step_name} recorded`, { description: bits.join(" · ") });
      onDone(res);
    } catch (e) {
      setError(describeError(e));
    }
  };

  const err = check.errors;
  return (
    <div className="flex flex-col gap-4">
      {fields.length ? (
        <Segmented aria-label="Entry mode" value={mode} onChange={switchMode} options={[{ value: "quick", label: "Quick · count only" }, { value: "full", label: "Full readings" }]} />
      ) : null}
      {quick && fields.length ? <Hint tone="sky">Only totals are needed. Blank readings get the nominal value and are tagged “Auto · nominal” on the dossier and reports.</Hint> : null}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Input" error={err.input}><DecimalInput kind="qty" decimals={4} value={counts.input} onValueChange={setCount("input")} /></Field>
        <Field label="Accepted" error={err.accepted}><DecimalInput kind="qty" decimals={4} value={counts.accepted} onValueChange={setCount("accepted")} /></Field>
        <Field label="Rejected" error={err.rejected}><DecimalInput kind="qty" decimals={4} value={counts.rejected} onValueChange={setCount("rejected")} /></Field>
        <Field label="Rework" error={err.rework}><DecimalInput kind="qty" decimals={4} value={counts.rework} onValueChange={setCount("rework")} /></Field>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[12.5px]" aria-live="polite">
        {err.sum ? <span className="font-medium text-warning-text">{err.sum}</span> : check.ok ? <span className="font-medium text-success-text">Units add up · {formatQty(check.total)} of {formatQty(counts.input)}</span> : null}
        {err.sum ? <Button size="sm" variant="ghost" onClick={() => setCounts(acceptRemainder(counts))}><CheckCheck /> Rest are accepted</Button> : null}
      </div>
      {check.needsDefect ? (
        <Field label="What was wrong with the rejected units?" required hint="Goes on the NCR that is raised automatically">
          <Textarea value={defect} onChange={(e) => setDefect(e.target.value)} placeholder="Bore oversize on 15 parts" />
        </Field>
      ) : null}
      <QcReadingsTable fields={fields} values={values} auto={auto} onChange={setReading} />
      {out > 0 ? <Hint tone="warning">{out} reading(s) out of tolerance — check the rejected count.</Hint> : null}
      {missing.length ? <p className="m-0 text-xs text-fg-muted">Still needed: {missing.map((f) => f.label).join(", ")}</p> : null}
      {canIso && (node?.config.instrument_required || (instruments.data?.length ?? 0) > 0) ? (
        <Field label="Gauge / instrument" required={Boolean(node?.config.instrument_required)} hint="Expired instruments can’t be used">
          <NativeSelect value={instrumentId} onChange={(e) => setInstrumentId(e.target.value)}>
            <option value="">{node?.config.instrument_required ? "Choose an instrument" : "None"}</option>
            {(instruments.data ?? []).map((i) => (
              <option key={i.id} value={i.id} disabled={i.status === "EXPIRED"}>{i.instrument_code} · {i.name}{i.status === "EXPIRED" ? " (expired)" : i.status === "DUE_SOON" ? ` (due in ${i.days_to_due} d)` : ""}</option>
            ))}
          </NativeSelect>
        </Field>
      ) : null}
      {step.is_locked ? (
        <Field label="Override reason" required hint="This step is signed off. Your reason is recorded in the audit log.">
          <Textarea value={override} onChange={(e) => setOverride(e.target.value)} />
        </Field>
      ) : null}
      <AdvancedSection title="Notes"><Textarea aria-label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} /></AdvancedSection>
      {error ? <Hint tone="danger" title="Not saved">{error}</Hint> : null}
      <div className="flex justify-end gap-2">
        {onCancel ? <Button onClick={onCancel}>Cancel</Button> : null}
        <Button variant="primary" size="lg" disabled={!ready} loading={execute.isPending} onClick={() => void submit()}>Save {quick ? "counts" : "entry"}</Button>
      </div>
    </div>
  );
}
