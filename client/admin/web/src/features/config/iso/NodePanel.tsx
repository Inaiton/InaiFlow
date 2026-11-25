"use client";

import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, Input, NativeSelect, Textarea } from "@/components/ui/input";
import { isDecimalString } from "@/lib/money";
import { BRANCHES, SHAPES, type BranchT, type WEdge, type WNode } from "./graph";
import { QcFieldsTable } from "./QcFieldsTable";

type Config = WNode["config"];

function Check({ label, checked, onChange, disabled }: { label: string; checked: boolean; onChange: (v: boolean) => void; disabled: boolean }) {
  return (
    <label className="flex items-center gap-2 text-[13px] text-ink-2">
      <input type="checkbox" className="size-4 accent-[#C35E49]" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export function NodePanel({ node, onChange, onDelete, readOnly }: { node: WNode; onChange: (n: WNode) => void; onDelete: () => void; readOnly: boolean }) {
  const c = node.config;
  const setC = (patch: Partial<Config>) => onChange({ ...node, config: { ...c, ...patch } });
  const isStep = node.shape === "RECTANGLE" || node.shape === "PARALLEL";
  const cycle = c.std_cycle_time_mins ?? "";
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-faint">{node.id}</span>
        {!readOnly ? (
          <Button size="sm" variant="danger-outline" onClick={onDelete}>
            <Trash2 /> Delete
          </Button>
        ) : null}
      </div>
      <Field label="Label">
        <Input value={node.label} disabled={readOnly} onChange={(e) => onChange({ ...node, label: e.target.value })} />
      </Field>
      <Field label="Shape">
        <NativeSelect value={node.shape} disabled={readOnly} onChange={(e) => onChange({ ...node, shape: e.target.value as WNode["shape"] })}>
          {SHAPES.map((s) => (
            <option key={s.shape} value={s.shape}>
              {s.label}
            </option>
          ))}
        </NativeSelect>
      </Field>
      {node.shape === "OVAL" ? (
        <Field label="Trigger">
          <NativeSelect value={c.trigger ?? "MANUAL"} disabled={readOnly} onChange={(e) => setC({ trigger: e.target.value })}>
            <option value="MANUAL">Manual launch</option>
            <option value="SCHEDULED_PERIOD_START">Scheduled period start</option>
            <option value="ON_GRN">On goods receipt (GRN)</option>
          </NativeSelect>
        </Field>
      ) : null}
      {isStep || node.shape === "DIAMOND" ? (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Assigned role">
            <Input value={c.assigned_role_code ?? ""} disabled={readOnly} onChange={(e) => setC({ assigned_role_code: e.target.value || null })} placeholder="OPERATOR" />
          </Field>
          <Field label="Std cycle (mins)">
            <Input value={cycle} disabled={readOnly} aria-invalid={cycle !== "" && !isDecimalString(cycle)} onChange={(e) => setC({ std_cycle_time_mins: e.target.value || null })} />
          </Field>
          <Field label="Machine" className="col-span-2">
            <Input value={c.machine ?? ""} disabled={readOnly} onChange={(e) => setC({ machine: e.target.value || null })} />
          </Field>
        </div>
      ) : null}
      {node.shape === "DIAMOND" ? (
        <>
          <Field label="Pass criteria">
            <NativeSelect value={c.pass_criteria?.mode ?? "ALL_IN_TOLERANCE"} disabled={readOnly} onChange={(e) => setC({ pass_criteria: { ...c.pass_criteria, mode: e.target.value } })}>
              <option value="ALL_IN_TOLERANCE">All readings in tolerance</option>
              <option value="MANUAL">Inspector decides</option>
              <option value="EXPRESSION">Expression</option>
            </NativeSelect>
          </Field>
          {c.pass_criteria?.mode === "EXPRESSION" ? (
            <Field label="Expression" hint="e.g. bore_dia >= 24.98 and bore_dia <= 25.02">
              <Input className="font-mono text-xs" value={c.pass_criteria.expression ?? ""} disabled={readOnly} onChange={(e) => setC({ pass_criteria: { mode: "EXPRESSION", expression: e.target.value } })} />
            </Field>
          ) : null}
          <Field label="Reject action">
            <NativeSelect value={c.reject_action ?? "NCR"} disabled={readOnly} onChange={(e) => setC({ reject_action: e.target.value })}>
              <option value="NCR">Raise NCR</option>
              <option value="SCRAP">Scrap</option>
              <option value="REWORK">Rework</option>
            </NativeSelect>
          </Field>
        </>
      ) : null}
      {isStep || node.shape === "DIAMOND" ? (
        <div className="space-y-1.5">
          <Check label="Calibrated instrument required" checked={!!c.instrument_required} disabled={readOnly} onChange={(v) => setC({ instrument_required: v })} />
          <Check label="Step can be skipped (reason required)" checked={!!c.skippable} disabled={readOnly} onChange={(v) => setC({ skippable: v })} />
        </div>
      ) : null}
      {isStep || node.shape === "DIAMOND" ? (
        <div>
          <p className="mb-1 text-[13px] font-medium text-muted">QC fields</p>
          <div className="-mx-1 overflow-x-auto">
            <QcFieldsTable fields={c.qc_fields ?? []} readOnly={readOnly} onChange={(qc_fields) => setC({ qc_fields })} />
          </div>
        </div>
      ) : null}
      <Field label="Notes">
        <Textarea value={c.notes ?? ""} disabled={readOnly} onChange={(e) => setC({ notes: e.target.value || null })} />
      </Field>
    </div>
  );
}

export function EdgePanel({ edge, onChange, onDelete, readOnly }: { edge: WEdge; onChange: (e: WEdge) => void; onDelete: () => void; readOnly: boolean }) {
  return (
    <div className="space-y-3">
      <p className="font-mono text-xs text-faint">
        {edge.source} → {edge.target}
      </p>
      <Field label="Branch">
        <NativeSelect value={edge.branch} disabled={readOnly} onChange={(e) => onChange({ ...edge, branch: e.target.value as BranchT })}>
          {BRANCHES.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Label (optional)">
        <Input value={edge.label ?? ""} disabled={readOnly} onChange={(e) => onChange({ ...edge, label: e.target.value || null })} />
      </Field>
      {!readOnly ? (
        <Button size="sm" variant="danger-outline" onClick={onDelete}>
          <Trash2 /> Delete edge
        </Button>
      ) : null}
    </div>
  );
}
