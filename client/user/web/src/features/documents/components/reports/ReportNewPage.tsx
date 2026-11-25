"use client";

import { Check, FilePlus2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button, Card, Combobox, Field, Hint, Input, KeyValue, NativeSelect, PageHeader, Skeleton } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useCreateDocument } from "../../api/documents";
import { useItemOptions, useRunContext, useRunOptions } from "../../api/context";
import { useFolder, type FolderOut } from "../../api/folders";
import { REPORT_DOC, useTemplates } from "../../api/templates";
import { useCurrentMonthFolder } from "../../lib/folders";
import { useDocsPath } from "../../paths";
import { FolderPickerDialog } from "../explorer/FolderPickerDialog";
import { ReportSteps } from "./ReportSteps";

/** Step 1 — choose template + run/step/item context (design Doc-Report-New). Server renders tokens on create. */
export function ReportNewPage() {
  const d = useDocsPath();
  const router = useRouter();
  const params = useSearchParams();
  const templates = useTemplates(REPORT_DOC);
  const [templateId, setTemplateId] = useState<string | null>(params.get("template"));
  const [blank, setBlank] = useState(params.get("blank") === "1");
  const [runQ, setRunQ] = useState("");
  const [itemQ, setItemQ] = useState("");
  const recent = useRunOptions("", "IN_PROGRESS");
  const runs = useRunOptions(runQ);
  const [runId, setRunId] = useState<string | null>(params.get("run"));
  const effectiveRun = runId ?? (params.get("run") === null && !blank ? recent.data?.items[0]?.id ?? null : null);
  const run = useRunContext(effectiveRun);
  const [stepId, setStepId] = useState<string | null>(params.get("step"));
  const items = useItemOptions(itemQ);
  const [itemId, setItemId] = useState<string | null>(params.get("item"));
  const [title, setTitle] = useState("");
  const [picked, setPicked] = useState<FolderOut | null>(null);
  const [choosing, setChoosing] = useState(false);
  const create = useCreateDocument();
  const runFolder = useFolder(run.data?.doc_folder_id ?? null);
  const monthFolder = useCurrentMonthFolder("OPERATIONS", !run.data?.doc_folder_id);
  const folder = picked ?? runFolder.data ?? monthFolder.data ?? null;

  const tpl = templates.data?.find((t) => t.id === templateId) ?? null;
  const r = run.data;
  const step = r?.steps.find((s) => s.id === stepId) ?? r?.steps.find((s) => s.status === "ACTIVE") ?? null;
  const node = step ? r?.graph_snapshot.nodes.find((n) => n.id === step.node_id) : undefined;
  const autoTitle = [tpl?.name ?? (blank ? "Report" : "Inspection report"), r?.run_title, step?.step_name].filter(Boolean).join(" · ");
  const ready = (blank || tpl) && folder;

  const submit = async () => {
    if (!folder) return;
    const ctx = { period_run_id: r?.id ?? null, step_id: step?.id ?? null, stock_item_id: r?.stock_item_id ?? itemId ?? null };
    const doc = await create.mutateAsync({
      folder_id: folder.id, title: title.trim() || autoTitle, source_type: blank ? "BLANK_ADHOC" : "INTERNAL_TEMPLATE",
      template_id: blank ? null : tpl?.id ?? null, context: blank ? null : ctx, rich_content: blank ? { blocks: [] } : null,
      linked_period_run_id: ctx.period_run_id, linked_step_id: ctx.step_id, linked_stock_item_id: ctx.stock_item_id,
    });
    router.push(d(`/editor/${doc.id}`));
  };

  const card = (key: string, name: string, desc: string, active: boolean, onClick: () => void) => (
    <button key={key} type="button" role="radio" aria-checked={active} onClick={onClick}
      className={cn("flex flex-col gap-1 rounded-xl border px-4 py-3 text-left", active ? "border-primary bg-primary-tint" : "border-line hover:border-line-strong")}>
      <span className="flex items-center gap-2 text-[13.5px] font-semibold text-fg">{active ? <Check className="size-4 text-primary" /> : null}{name}</span>
      <span className="text-xs text-fg-muted">{desc}</span>
    </button>
  );

  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Documents", href: d() }, { label: "Inspection report", href: d("/editor") }, { label: "Choose" }]}
        title="New inspection report" description="Three short steps — most of it is filled in for you"
        actions={<><Button onClick={() => router.back()}>Cancel</Button><Button variant="primary" disabled={!ready} loading={create.isPending} onClick={() => void submit()}><FilePlus2 /> Next: Fill in the results</Button></>} />
      <ReportSteps current={0} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex flex-col gap-4">
          <Card title="Choose a template" description="Not sure? Incoming inspection or first article fits most shop-floor checks.">
            {!templates.data ? <Skeleton className="h-28" /> : (
              <div role="radiogroup" aria-label="Template" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {templates.data.map((t) => card(t.id, t.name, t.description ?? (t.is_system_default ? "Standard template" : "Your template"), !blank && t.id === templateId, () => { setTemplateId(t.id); setBlank(false); }))}
                {card("blank", "Blank report", "Start from an empty page — no template.", blank, () => { setBlank(true); setTemplateId(null); })}
              </div>
            )}
          </Card>
          {!blank ? (
            <Card title="Which job is it for?" description={params.get("run") ? undefined : "Pre-selected from your most recent active run"}>
              <Field label="Production run">
                <Combobox value={effectiveRun} onValueChange={(v) => { setRunId(v); setStepId(null); }} onSearch={setRunQ} placeholder="Choose a run (optional)"
                  options={[...(r && !runs.data?.items.some((x) => x.id === r.id) ? [{ value: r.id, label: r.run_title, hint: r.status }] : []), ...(runs.data?.items ?? []).map((x) => ({ value: x.id, label: x.run_title, hint: `${x.stock_item_name ?? x.workflow_name} · ${x.status.replace("_", " ").toLowerCase()}` }))]} />
              </Field>
              {r ? (
                <Field label="Workflow step" hint="Readings and counts come from this step">
                  <NativeSelect value={step?.id ?? ""} onChange={(e) => setStepId(e.target.value || null)}>
                    {[...r.steps].sort((a, b) => a.sequence - b.sequence).map((s) => <option key={s.id} value={s.id}>{s.step_name}</option>)}
                  </NativeSelect>
                </Field>
              ) : (
                <Field label="Item" hint="Without a run, pick the part the report is about">
                  <Combobox value={itemId} onValueChange={setItemId} onSearch={setItemQ} placeholder="Choose an item (optional)"
                    options={(items.data?.items ?? []).map((i) => ({ value: i.id, label: i.name, hint: i.sku_code ?? "" }))} />
                </Field>
              )}
              <Hint tone="sky">We’ll fill in the item, drawing, quantities and the spec for each parameter for you.</Hint>
            </Card>
          ) : null}
        </div>
        <Card title="Your report" className="self-start">
          <KeyValue rows={[
            ["Template", blank ? "Blank" : tpl?.name ?? "—"],
            ["Run", r?.run_title ?? "—"],
            ["Step", step?.step_name ?? "—"],
            ["Parameters", node?.config.qc_fields?.length ? `${node.config.qc_fields.length} from the workflow` : "—"],
            ["Saves to", <button key="f" type="button" className="text-link" onClick={() => setChoosing(true)}>{folder?.name ?? "Choose folder"}</button>],
          ]} />
          <Field label="Title"><Input value={title} placeholder={autoTitle} onChange={(e) => setTitle(e.target.value)} /></Field>
        </Card>
      </div>
      <FolderPickerDialog open={choosing} onOpenChange={setChoosing} title="Save report to…" onPick={(f) => { setPicked(f); setChoosing(false); }} />
    </div>
  );
}
