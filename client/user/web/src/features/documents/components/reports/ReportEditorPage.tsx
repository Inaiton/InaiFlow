"use client";

import { ArrowRight, Eye } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useReducer, useState } from "react";
import { Button, Card, ErrorState, Hint, Input, PageHeader, Skeleton } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { useCan } from "@/core/permissions/Can";
import { useShortcut, useShortcutScope } from "@/core/shortcuts/registry";
import { useDocument, useUpdateDocument, type DocumentOut } from "../../api/documents";
import { useRunContext } from "../../api/context";
import { blocksReducer, normalizeBlocks, qcRows, type ReportBlock } from "../../lib/blocks";
import { qcRowsFromStep } from "../../lib/qc-prefill";
import { useDocsPath } from "../../paths";
import { BlockEditor } from "../blocks/BlockEditor";
import { BlockView } from "../blocks/BlockView";
import { ReportSteps } from "./ReportSteps";

type Run = Schemas["RunOut"];

/** Empty QC tables get the linked step's readings (nominal auto-fill for unmeasured fields). */
function prefill(doc: DocumentOut, run: Run | undefined): ReportBlock[] {
  const blocks = normalizeBlocks(doc.rich_content);
  const step = run?.steps.find((s) => s.id === doc.linked_step_id);
  const fields = step ? run?.graph_snapshot.nodes.find((n) => n.id === step.node_id)?.config.qc_fields ?? [] : [];
  if (!fields.length) return blocks;
  return blocks.map((b) => (b.type === "qc_table" && qcRows(b).length === 0 ? { ...b, data: { ...(b.data as object), rows: qcRowsFromStep(fields, step) } } : b));
}

/** Step 2 — fill in the results (design Doc-Editor): block editor + live preview, autosave. */
export function ReportEditorPage({ docId }: { docId: string }) {
  const doc = useDocument(docId);
  const run = useRunContext(doc.data?.linked_period_run_id ?? null);
  if (doc.isError) return <ErrorState message={describeError(doc.error)} onRetry={() => void doc.refetch()} />;
  if (!doc.data || (doc.data.linked_period_run_id && run.isPending && run.fetchStatus !== "idle")) return <Skeleton className="h-[70vh]" />;
  return <Editor key={doc.data.id} doc={doc.data} run={run.data} />;
}

function Editor({ doc, run }: { doc: DocumentOut; run: Run | undefined }) {
  const d = useDocsPath();
  const router = useRouter();
  const canEdit = useCan("documents.editor", "WRITE");
  const readOnly = !canEdit || doc.approval_status !== "DRAFT";
  const [blocks, dispatch] = useReducer(blocksReducer, undefined, () => prefill(doc, run));
  const [title, setTitle] = useState(doc.title);
  const [state, setState] = useState<"saved" | "saving" | "error" | "idle">("idle");
  const save = useUpdateDocument(doc.id, { silent: true });
  const [saved, setSaved] = useState({ snap: JSON.stringify(normalizeBlocks(doc.rich_content)), title: doc.title });
  const snap = JSON.stringify(blocks);
  const dirty = snap !== saved.snap || title !== saved.title;

  const flush = useCallback(async () => {
    if (readOnly || !dirty) return true;
    setState("saving");
    try {
      const t = title.trim() || saved.title;
      await save.mutateAsync({ rich_content: { blocks }, title: t });
      setSaved({ snap, title });
      setState("saved");
      return true;
    } catch {
      setState("error");
      return false;
    }
  }, [readOnly, dirty, title, saved.title, save, blocks, snap]);

  useEffect(() => {
    if (!dirty || readOnly) return;
    const t = setTimeout(() => void flush(), 1500);
    return () => clearTimeout(t);
  }, [dirty, readOnly, flush]);

  useShortcutScope("report-editor");
  useShortcut("ctrl+s", () => void flush(), { scope: "report-editor", description: "Save draft", allowInInputs: true });
  const next = async () => { if (await flush()) router.push(d(`/editor/${doc.id}/review`)); };
  const auto = blocks.flatMap((b) => (b.type === "qc_table" ? qcRows(b) : [])).filter((r) => r.auto).length;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Documents", href: d() }, { label: "Inspection report", href: d("/editor") }, { label: "Fill in the results" }]}
        title="Fill in the results"
        description={state === "saving" ? "Saving…" : state === "saved" ? "All changes saved" : state === "error" ? "Couldn’t save — check your connection; we’ll retry on the next change" : doc.folder_path.join(" / ")}
        actions={<>
          {!readOnly ? <Button onClick={() => void flush()} loading={state === "saving"}>Save draft</Button> : null}
          <Button variant="primary" onClick={() => void next()}>Next: Review & sign <ArrowRight /></Button>
        </>} />
      <ReportSteps current={1} />
      {readOnly ? <Hint tone="sky" title="This report is locked">It is {doc.approval_status.replace("_", " ").toLowerCase()}. <Link href={d(`/editor/${doc.id}/review`)}>Open the review page</Link> to see approvals or start a new revision.</Hint> : null}
      {auto ? <Hint tone="sky">Anything you don’t measure keeps the nominal value and is tagged <strong>AUTO</strong>. Type a real reading to replace it.</Hint> : null}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-3">
          <Input aria-label="Report title" className="text-base font-semibold" value={title} disabled={readOnly} onChange={(e) => setTitle(e.target.value)} />
          <BlockEditor blocks={blocks} dispatch={dispatch} readOnly={readOnly} />
        </div>
        <Card title={<span className="flex items-center gap-1.5"><Eye className="size-4" /> Live preview</span>} description="Updates as you type · A4" className="self-start xl:sticky xl:top-4">
          <BlockView blocks={blocks} className="px-5 py-5 text-[12px]" />
        </Card>
      </div>
    </div>
  );
}
