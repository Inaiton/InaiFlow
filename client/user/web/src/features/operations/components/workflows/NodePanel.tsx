"use client";

import { Trash2 } from "lucide-react";
import { AdvancedSection, Button, DecimalInput, Field, Hint, Input, NativeSelect, SwitchRow, Textarea } from "@/components/ui";
import { DocumentPicker, REPORT_DOC, useTemplates } from "@/features/documents/public";
import { SHAPE_HINT, SHAPE_LABEL, type Branch, type WorkflowEdge, type WorkflowNode } from "../../lib/graph";
import { useGodowns, useRoleLookup } from "../../api/lookups";
import { QcFieldsEditor } from "./QcFieldsEditor";
import type { CanvasStore } from "./useFlowchartCanvasStore";

const TRIGGERS = [["MANUAL", "Started by hand"], ["SCHEDULED_PERIOD_START", "Start of every month"], ["ON_GRN", "On goods receipt (GRN)"]];
const REJECT_ACTIONS = [["SCRAP_NCR", "Scrap + raise NCR"], ["SCRAP", "Scrap only"], ["REWORK", "Send to rework"], ["NCR", "Raise NCR, hold units"]];
const PASS_MODES = [["ALL_IN_TOLERANCE", "Every reading within tolerance"], ["MANUAL", "Inspector decides (counts only)"], ["EXPRESSION", "Custom rule"]];

/** Node config side panel (design Ops-WF-NodeProcess). Common settings first, rare ones under Advanced. */
export function NodePanel({ node, store, readOnly, issues }: { node: WorkflowNode; store: CanvasStore; readOnly: boolean; issues: string[] }) {
  const c = node.config;
  const set = (config: Partial<WorkflowNode["config"]>) => store.updateNode(node.id, { config });
  const roles = useRoleLookup();
  const godowns = useGodowns();
  const templates = useTemplates(REPORT_DOC);
  const work = node.shape === "RECTANGLE" || node.shape === "PARALLEL" || node.shape === "DIAMOND";
  return (
    <fieldset disabled={readOnly} className="flex min-w-0 flex-col gap-3.5">
      <div>
        <p className="m-0 text-[11px] font-semibold tracking-wide text-fg-muted uppercase">{SHAPE_LABEL[node.shape]}</p>
        <p className="m-0 text-xs text-fg-muted">{SHAPE_HINT[node.shape]}</p>
      </div>
      {issues.length ? <Hint tone="danger" title="Fix before publishing">{issues.join(" · ")}</Hint> : null}
      <Field label="Step name" required><Input value={node.label} onChange={(e) => store.updateNode(node.id, { label: e.target.value })} /></Field>
      {node.shape === "OVAL" ? (
        <Field label="How does a run start?">
          <NativeSelect value={c.trigger ?? "MANUAL"} onChange={(e) => set({ trigger: e.target.value })}>
            {TRIGGERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </NativeSelect>
        </Field>
      ) : null}
      {work ? (
        <Field label="Who does it" hint={roles.data ? undefined : "Role code, e.g. OPERATOR"}>
          {roles.data ? (
            <NativeSelect value={c.assigned_role_code ?? ""} onChange={(e) => set({ assigned_role_code: e.target.value || null })}>
              <option value="">Anyone with run access</option>
              {roles.data.map((r) => <option key={r.id} value={r.role_code}>{r.role_name}</option>)}
            </NativeSelect>
          ) : <Input value={c.assigned_role_code ?? ""} onChange={(e) => set({ assigned_role_code: e.target.value || null })} />}
        </Field>
      ) : null}
      {node.shape === "DIAMOND" ? (
        <>
          <Field label="Pass if">
            <NativeSelect value={c.pass_criteria?.mode ?? "ALL_IN_TOLERANCE"} onChange={(e) => set({ pass_criteria: { mode: e.target.value, expression: c.pass_criteria?.expression ?? null } })}>
              {PASS_MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </NativeSelect>
          </Field>
          {c.pass_criteria?.mode === "EXPRESSION" ? (
            <Field label="Rule" hint="e.g. bore >= 39.98 and bore <= 40.02"><Input value={c.pass_criteria.expression ?? ""} onChange={(e) => set({ pass_criteria: { mode: "EXPRESSION", expression: e.target.value } })} /></Field>
          ) : null}
          <Field label="Rejected units go to">
            <NativeSelect value={c.reject_action ?? "SCRAP_NCR"} onChange={(e) => set({ reject_action: e.target.value })}>
              {REJECT_ACTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </NativeSelect>
          </Field>
        </>
      ) : null}
      {work ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-[12.5px] font-medium text-fg-2">Readings to record</span>
          <QcFieldsEditor value={c.qc_fields ?? []} onChange={(qc_fields) => set({ qc_fields })} readOnly={readOnly} />
        </div>
      ) : null}
      {node.shape === "TERMINATOR" ? (
        <Field label="Commit finished units to" hint="Finished-goods godown in Accounts">
          <NativeSelect value={c.commit_godown_id ?? ""} onChange={(e) => set({ commit_godown_id: e.target.value || null })}>
            <option value="">Default finished-goods godown</option>
            {(godowns.data ?? []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </NativeSelect>
        </Field>
      ) : null}
      {node.shape !== "OVAL" ? (
        <AdvancedSection title="Advanced" description="Machine, gauge, SOP, report and skipping">
          <div className="flex flex-col gap-3">
            {work ? (
              <>
                <Field label="Machine"><Input value={c.machine ?? ""} onChange={(e) => set({ machine: e.target.value || null })} placeholder="LL20-03" /></Field>
                <Field label="Standard cycle time">
                  <DecimalInput kind="qty" suffix="min" value={c.std_cycle_time_mins ?? ""} onValueChange={(v) => set({ std_cycle_time_mins: v })} />
                </Field>
                <SwitchRow label="Gauge required" description="Operator must pick a calibrated instrument" checked={c.instrument_required ?? false} onCheckedChange={(v) => set({ instrument_required: v })} disabled={readOnly} />
              </>
            ) : null}
            <SwitchRow label="Can be skipped" description="Allows ‘Skip’ with a reason during a run" checked={c.skippable ?? false} onCheckedChange={(v) => set({ skippable: v })} disabled={readOnly} />
            <Field label="Work instruction (SOP)"><DocumentPicker value={c.sop_document_id} onChange={(id) => set({ sop_document_id: id })} isoOnly disabled={readOnly} /></Field>
            <Field label="Step report template">
              <NativeSelect value={c.report_template_id ?? ""} onChange={(e) => set({ report_template_id: e.target.value || null })}>
                <option value="">None</option>
                {(templates.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </NativeSelect>
            </Field>
            <Field label="Notes"><Textarea value={c.notes ?? ""} onChange={(e) => set({ notes: e.target.value || null })} /></Field>
          </div>
        </AdvancedSection>
      ) : null}
      {!readOnly ? <Button variant="destructive" onClick={() => store.removeNode(node.id)}><Trash2 /> Delete step</Button> : null}
    </fieldset>
  );
}

const BRANCHES: [Branch, string][] = [["PASS", "PASS — accepted units"], ["REJECT", "REJECT — rejected units"], ["REWORK", "REWORK — loop back"], ["DEFAULT", "DEFAULT — always"]];

export function EdgePanel({ edge, store, readOnly }: { edge: WorkflowEdge; store: CanvasStore; readOnly: boolean }) {
  return (
    <fieldset disabled={readOnly} className="flex flex-col gap-3.5">
      <p className="m-0 text-[11px] font-semibold tracking-wide text-fg-muted uppercase">Connection</p>
      <Field label="Which units follow this line">
        <NativeSelect value={edge.branch} onChange={(e) => store.updateEdge(edge.id, { branch: e.target.value as Branch })}>
          {BRANCHES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </NativeSelect>
      </Field>
      <Field label="Label" hint="Optional, e.g. ‘Accepted’"><Input value={edge.label ?? ""} onChange={(e) => store.updateEdge(edge.id, { label: e.target.value || null })} /></Field>
      {!readOnly ? <Button variant="destructive" onClick={() => store.removeEdge(edge.id)}><Trash2 /> Remove connection</Button> : null}
    </fieldset>
  );
}
