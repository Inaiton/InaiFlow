"use client";

import { Copy, Eye } from "lucide-react";
import { useRouter } from "next/navigation";
import { useReducer, useState } from "react";
import { toast } from "sonner";
import { Button, Card, Combobox, ErrorState, Field, Hint, Input, PageHeader, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { useCan } from "@/core/permissions/Can";
import { useRunContext, useRunOptions } from "../../api/context";
import { useCloneTemplate, usePreviewTemplate, useTemplate, useTemplateTokens, useUpdateTemplate, type TemplateOut } from "../../api/templates";
import { blocksReducer, normalizeBlocks, tokensIn, type ReportBlock } from "../../lib/blocks";
import { useDocsPath } from "../../paths";
import { BlockEditor } from "../blocks/BlockEditor";
import { BlockView } from "../blocks/BlockView";

const bare = (t: string) => t.replace(/^\{\{\s*|\s*\}\}$/g, "");

/** /documents/templates/[id] — custom template builder: same block editor + token picker + preview against a run (design Doc-Template-Builder). */
export function TemplateBuilder({ templateId }: { templateId: string }) {
  const t = useTemplate(templateId);
  if (t.isError) return <ErrorState message={describeError(t.error)} onRetry={() => void t.refetch()} />;
  if (!t.data) return <Skeleton className="h-[70vh]" />;
  return <Builder key={t.data.id} tpl={t.data} />;
}

function Builder({ tpl }: { tpl: TemplateOut }) {
  const d = useDocsPath();
  const router = useRouter();
  const canWrite = useCan("documents.templates", "WRITE");
  const readOnly = tpl.is_system_default || !canWrite;
  const [blocks, dispatch] = useReducer(blocksReducer, tpl.content_schema, normalizeBlocks);
  const [name, setName] = useState(tpl.name);
  const [description, setDescription] = useState(tpl.description ?? "");
  const save = useUpdateTemplate(tpl.id);
  const clone = useCloneTemplate();
  const tokens = useTemplateTokens();
  const preview = usePreviewTemplate(tpl.id);
  const [runQ, setRunQ] = useState("");
  const runs = useRunOptions(runQ);
  const [runId, setRunId] = useState<string | null>(null);
  const run = useRunContext(runId);
  const [rendered, setRendered] = useState<{ blocks: ReportBlock[]; warnings: string[] } | null>(null);
  const used = new Set(tokensIn(blocks));
  const groups = Object.entries((tokens.data ?? []).reduce<Record<string, typeof tokens.data>>((m, k) => ({ ...m, [k.group]: [...(m[k.group] ?? []), k] }), {}));

  const doSave = () => save.mutateAsync({ name: name.trim() || tpl.name, description: description || null, content_schema: { blocks } });
  const doPreview = async () => {
    if (!readOnly) await doSave();
    const step = run.data?.steps.find((s) => s.executed_at) ?? run.data?.steps[0];
    const out = await preview.mutateAsync({ period_run_id: runId, step_id: step?.id ?? null, stock_item_id: run.data?.stock_item_id ?? null });
    setRendered({ blocks: normalizeBlocks(out.rich_content), warnings: out.warnings });
  };
  const copyToken = async (token: string) => {
    const s = `{{${bare(token)}}}`;
    try { await navigator.clipboard.writeText(s); toast.success(`Copied ${s}`, { description: "Paste it into any text field" }); } catch { toast.message(s); }
  };

  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Documents", href: d() }, { label: "Templates", href: d("/templates") }, { label: tpl.name }]}
        title={tpl.is_system_default ? tpl.name : "Template builder"} description={tpl.is_system_default ? "Standard templates are read-only — clone one to adapt it." : "Text can contain {{tokens}} that fill in from the run, step, item and accounts"}
        actions={readOnly
          ? (canWrite ? <Button variant="primary" loading={clone.isPending} onClick={async () => router.push(d(`/templates/${(await clone.mutateAsync(tpl.id)).id}`))}><Copy /> Clone to edit</Button> : null)
          : <Button variant="primary" loading={save.isPending} onClick={() => void doSave()}>Save template</Button>} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex flex-col gap-3">
          <Card>
            <Field label="Name" required><Input disabled={readOnly} value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="When to use it"><Input disabled={readOnly} value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
          </Card>
          <BlockEditor blocks={blocks} dispatch={dispatch} readOnly={readOnly} />
          <Card title={<span className="flex items-center gap-1.5"><Eye className="size-4" /> Preview with real data</span>}>
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-64 flex-1"><Combobox value={runId} onValueChange={setRunId} onSearch={setRunQ} placeholder="Pick a run to preview with" options={(runs.data?.items ?? []).map((r) => ({ value: r.id, label: r.run_title }))} /></div>
              <Button loading={preview.isPending} onClick={() => void doPreview()}>Preview</Button>
            </div>
            {rendered?.warnings.length ? <Hint tone="warning" title="Unknown tokens render empty">{rendered.warnings.join(" · ")}</Hint> : null}
            {rendered ? <BlockView blocks={rendered.blocks} className="px-5 py-5 text-[12px]" /> : <BlockView blocks={blocks} className="px-5 py-5 text-[12px]" />}
          </Card>
        </div>
        <Card title="Data fields" description="Click to copy, then paste into a block" className="self-start xl:sticky xl:top-4">
          {!tokens.data ? <Skeleton className="h-40" /> : groups.map(([g, list]) => (
            <section key={g} aria-label={g} className="flex flex-col gap-1">
              <h3 className="m-0 text-[11px] font-semibold tracking-wide text-fg-muted uppercase">{g}</h3>
              {(list ?? []).map((k) => (
                <button key={k.token} type="button" onClick={() => void copyToken(k.token)} title={`e.g. ${k.sample}`}
                  className="flex items-center justify-between gap-2 rounded-md px-2 py-1 text-left text-[12.5px] hover:bg-subtle">
                  <span className="truncate text-fg-2">{k.label}</span>
                  <code className={used.has(bare(k.token)) ? "text-primary-text" : "text-fg-muted"}>{k.token}</code>
                </button>
              ))}
            </section>
          ))}
        </Card>
      </div>
    </div>
  );
}
