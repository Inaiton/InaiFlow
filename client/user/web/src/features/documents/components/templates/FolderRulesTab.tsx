"use client";

import { FolderLock, FolderPlus, Plus, X } from "lucide-react";
import { useState } from "react";
import { Button, DatePicker, ErrorState, Hint, Input, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { monthKey, monthStart } from "@/core/dates";
import { useCan } from "@/core/permissions/Can";
import { useEnsureMonth } from "../../api/folders";
import { MONTHLY_FOLDER_RULE, useTemplates, useUpdateTemplate, type TemplateOut } from "../../api/templates";

type Node = { name: string; children?: Node[] };
const rec = (v: unknown): Record<string, unknown> => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {});
const nodes = (v: unknown): Node[] => (Array.isArray(v) ? v.map((n) => ({ name: String(rec(n).name ?? ""), children: nodes(rec(n).children) })) : []);

/** Monthly auto-folder blueprint (MONTHLY_FOLDER_RULE): system sub-folders are fixed; custom ones (one level of children) are editable. */
export function FolderRulesTab() {
  const rules = useTemplates(MONTHLY_FOLDER_RULE);
  if (rules.isError) return <ErrorState message={describeError(rules.error)} onRetry={() => void rules.refetch()} />;
  if (!rules.data) return <Skeleton className="h-40" />;
  const rule = rules.data[0];
  return (
    <div className="flex flex-col gap-4 pt-2">
      {rule ? <RuleEditor key={rule.id} rule={rule} /> : <Hint tone="warning">No monthly folder rule found for this organization.</Hint>}
      <EnsureMonth />
    </div>
  );
}

function RuleEditor({ rule }: { rule: TemplateOut }) {
  const canWrite = useCan("documents.templates", "WRITE");
  const save = useUpdateTemplate(rule.id);
  const schema = rec(rule.content_schema);
  const system = nodes(schema.subfolders);
  const [custom, setCustom] = useState<Node[]>(nodes(schema.custom));
  const set = (i: number, n: Node) => setCustom((c) => c.map((x, j) => (j === i ? n : x)));
  const clean = (ns: Node[]): Node[] => ns.filter((n) => n.name.trim()).map((n) => ({ name: n.name.trim(), ...(n.children?.length ? { children: clean(n.children) } : {}) }));
  return (
    <section aria-label="Folder blueprint" className="flex flex-col gap-3">
      <p className="m-0 text-[13px] text-fg-muted">Created on the 1st of every month inside <strong>/FY … / MM - Month YYYY</strong>, and for every new run.</p>
      <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
        {system.map((n) => <li key={n.name} className="flex items-center gap-2 rounded-lg bg-canvas px-3 py-2 text-[13px] text-fg-2"><FolderLock className="size-4 text-fg-muted" />{n.name}<span className="ml-auto text-[11px] text-fg-faint">system</span></li>)}
        {custom.map((n, i) => (
          <li key={i} className="flex flex-col gap-1.5 rounded-lg border border-line px-3 py-2">
            <div className="flex items-center gap-2">
              <FolderPlus className="size-4 text-sky-text" />
              <Input aria-label="Folder name" disabled={!canWrite} value={n.name} onChange={(e) => set(i, { ...n, name: e.target.value })} placeholder="QC logs" />
              {canWrite ? <Button size="icon-sm" variant="ghost" aria-label="Remove folder" onClick={() => setCustom((c) => c.filter((_, j) => j !== i))}><X /></Button> : null}
            </div>
            {(n.children ?? []).map((k, j) => (
              <div key={j} className="ml-6 flex items-center gap-2">
                <Input aria-label="Sub-folder name" disabled={!canWrite} value={k.name} onChange={(e) => set(i, { ...n, children: (n.children ?? []).map((x, m) => (m === j ? { name: e.target.value } : x)) })} />
                {canWrite ? <Button size="icon-sm" variant="ghost" aria-label="Remove sub-folder" onClick={() => set(i, { ...n, children: (n.children ?? []).filter((_, m) => m !== j) })}><X /></Button> : null}
              </div>
            ))}
            {canWrite ? <Button size="sm" variant="ghost" className="ml-6 self-start" onClick={() => set(i, { ...n, children: [...(n.children ?? []), { name: "" }] })}><Plus /> Sub-folder</Button> : null}
          </li>
        ))}
      </ul>
      {canWrite ? (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => setCustom((c) => [...c, { name: "" }])}><Plus /> Add folder</Button>
          <Button size="sm" variant="primary" loading={save.isPending} onClick={() => save.mutate({ content_schema: { ...schema, custom: clean(custom) } })}>Save blueprint</Button>
        </div>
      ) : null}
    </section>
  );
}

function EnsureMonth() {
  const canFull = useCan("documents.templates", "FULL");
  const ensure = useEnsureMonth();
  const [month, setMonth] = useState(monthKey(new Date()));
  if (!canFull) return null;
  return (
    <section aria-label="Create month folders" className="flex flex-wrap items-end gap-2 border-t border-line pt-4">
      <div className="flex flex-col gap-1"><span className="text-[12.5px] font-medium text-fg-2">Create a month’s folders now</span><DatePicker mode="month" value={month} onValueChange={(v) => v && setMonth(v)} /></div>
      <Button loading={ensure.isPending} onClick={() => ensure.mutate(monthStart(month))}>Create folders</Button>
    </section>
  );
}
