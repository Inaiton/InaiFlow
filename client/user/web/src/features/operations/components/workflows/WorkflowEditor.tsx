"use client";

import { CheckCircle2, CopyPlus, History, Rocket, ShieldCheck } from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, ConfirmDialog, ErrorState, Hint, PageHeader, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { useCan } from "@/core/permissions/Can";
import { useShortcut, useShortcutScope } from "@/core/shortcuts/registry";
import { useNewWorkflowVersion, usePublishWorkflow, useSaveWorkflow, useValidateWorkflow, useWorkflow } from "../../api/workflows";
import { issuesByNode, validateGraph, type ValidationIssue } from "../../lib/graph";
import { useOpsPath } from "../../paths";
import { EdgePanel, NodePanel } from "./NodePanel";
import { ShapePalette } from "./ShapePalette";
import { createCanvasStore, useFlowchartCanvasStore } from "./useFlowchartCanvasStore";
import { ValidationList } from "./ValidationList";
import { VersionsSheet } from "./VersionsSheet";

const FlowCanvas = dynamic(() => import("../shared/FlowCanvas"), { ssr: false, loading: () => <Skeleton className="h-full w-full" /> });

type SaveState = "idle" | "saving" | "saved" | "error";

/** /operations/workflows/[id] — flowchart studio (design Ops-Workflow / WF-*). */
export function WorkflowEditor({ workflowId }: { workflowId: string }) {
  const wf = useWorkflow(workflowId);
  if (wf.isError) return <ErrorState message={describeError(wf.error)} onRetry={() => void wf.refetch()} />;
  if (!wf.data) return <Skeleton className="h-[70vh]" />;
  return <Editor key={`${wf.data.id}-${wf.data.status}`} wf={wf.data} />;
}

function Editor({ wf }: { wf: NonNullable<ReturnType<typeof useWorkflow>["data"]> }) {
  const p = useOpsPath();
  const router = useRouter();
  const canWrite = useCan("operations.workflows", "WRITE");
  const canPublish = useCan("operations.workflows", "FULL");
  const published = wf.status !== "DRAFT";
  const readOnly = published || !canWrite;
  const store = useMemo(() => createCanvasStore(wf.graph_definition, readOnly), [wf.graph_definition, readOnly]);
  const graph = useFlowchartCanvasStore(store, (s) => s.graph);
  const selected = useFlowchartCanvasStore(store, (s) => s.selected);
  const revision = useFlowchartCanvasStore(store, (s) => s.revision);
  const save = useSaveWorkflow(wf.id);
  const validate = useValidateWorkflow(wf.id);
  const publish = usePublishWorkflow(wf.id);
  const newVersion = useNewWorkflowVersion(wf.id);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [serverIssues, setServerIssues] = useState<{ errors: ValidationIssue[]; warnings: ValidationIssue[] } | null>(null);
  const [confirmPublish, setConfirmPublish] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const savedRev = useRef(0);

  const flush = useCallback(async () => {
    const s = store.get();
    if (s.readOnly || s.revision === savedRev.current) return true;
    setSaveState("saving");
    try {
      await save.mutateAsync({ graph_definition: s.graph });
      savedRev.current = s.revision;
      setSaveState("saved");
      return true;
    } catch {
      setSaveState("error");
      return false;
    }
  }, [save, store]);

  useEffect(() => {
    if (readOnly || revision === savedRev.current) return;
    setServerIssues(null);
    const t = setTimeout(() => void flush(), 1200);
    return () => clearTimeout(t);
  }, [revision, readOnly, flush]);

  useShortcutScope("workflow-studio");
  useShortcut("ctrl+s", () => void flush(), { scope: "workflow-studio", description: "Save draft", allowInInputs: true });

  const local = useMemo(() => validateGraph(graph), [graph]);
  const issues = serverIssues ?? local;
  const byNode = useMemo(() => issuesByNode([...issues.errors, ...issues.warnings]), [issues]);
  const decorate = useCallback((id: string) => ({ issues: byNode.get(id) }), [byNode]);
  const selNode = selected?.kind === "node" ? graph.nodes.find((n) => n.id === selected.id) : undefined;
  const selEdge = selected?.kind === "edge" ? graph.edges.find((e) => e.id === selected.id) : undefined;

  const runValidate = async () => {
    if (!(await flush())) return null;
    const r = await validate.mutateAsync();
    setServerIssues({ errors: r.errors, warnings: r.warnings });
    return r;
  };
  const doPublish = async () => {
    const r = await runValidate();
    if (r?.valid) await publish.mutateAsync();
    setConfirmPublish(false);
  };
  const createVersion = async () => {
    const out = await newVersion.mutateAsync();
    router.push(p(`/workflows/${out.id}`));
  };

  const status = saveState === "saving" ? "Saving…" : saveState === "saved" ? "All changes saved" : saveState === "error" ? "Couldn’t save — retrying on next change" : "Draft";
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        crumbs={[{ label: "Operations", href: p() }, { label: "Workflow studio", href: p("/workflows") }, { label: `${wf.name} · v${wf.version}` }]}
        title={<span className="flex items-center gap-2">{wf.name} <Badge tone={published ? "success" : "indigo"}>v{wf.version} · {published ? "Published" : "Draft"}</Badge></span>}
        description={published ? `${wf.active_run_count} active run(s) use this version${wf.stock_item_name ? ` · ${wf.stock_item_name}` : ""}` : status}
        actions={
          <>
            <Button onClick={() => setVersionsOpen(true)}><History /> Versions</Button>
            {!published ? <Button onClick={() => void runValidate()} loading={validate.isPending}><ShieldCheck /> Check</Button> : null}
            {published ? (
              canWrite ? <Button variant="primary" onClick={() => void createVersion()} loading={newVersion.isPending}><CopyPlus /> Create new version</Button> : null
            ) : canPublish ? (
              <Button variant="primary" onClick={() => setConfirmPublish(true)}><Rocket /> Publish</Button>
            ) : null}
          </>
        }
      />
      {published ? (
        <Hint tone="sky" title="Published versions are read-only">Runs pin this exact version. To change the flow, create v{wf.version + 1} — active runs keep using v{wf.version}.</Hint>
      ) : null}
      <div className="grid min-h-[620px] gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="relative overflow-hidden rounded-2xl border border-line bg-canvas" style={{ height: "min(72vh, 760px)" }}>
          {!readOnly ? <ShapePalette onAdd={(s) => store.addNode(s)} /> : null}
          <FlowCanvas
            graph={graph}
            readOnly={readOnly}
            selectedId={selected?.id}
            decorate={decorate}
            onSelect={store.select}
            onMove={store.moveNodes}
            onConnect={store.connect}
            onRemoveEdge={store.removeEdge}
            onRemoveNode={store.removeNode}
          />
        </div>
        <aside className="flex max-h-[min(72vh,760px)] flex-col gap-4 overflow-y-auto rounded-2xl border border-line bg-surface px-4 py-4">
          {selNode ? <NodePanel node={selNode} store={store} readOnly={readOnly} issues={byNode.get(selNode.id) ?? []} />
            : selEdge ? <EdgePanel edge={selEdge} store={store} readOnly={readOnly} />
            : (
              <div className="flex flex-col gap-3">
                <p className="m-0 text-[13px] text-fg-muted">{readOnly ? "Click a step to see its settings." : "Add steps from the toolbar, drag from a step’s bottom dot to connect it, then click a step to configure it."}</p>
                {issues.errors.length === 0 && issues.warnings.length === 0 ? (
                  <p className="m-0 flex items-center gap-1.5 text-[13px] text-success-text"><CheckCircle2 className="size-4" /> Ready to publish</p>
                ) : <ValidationList issues={issues} onPick={(id) => store.select({ kind: "node", id })} />}
              </div>
            )}
        </aside>
      </div>
      <ConfirmDialog
        open={confirmPublish}
        onOpenChange={setConfirmPublish}
        title={`Publish v${wf.version}?`}
        description="We’ll check the flow first. After publishing, this version is locked and can be used to launch runs."
        confirmLabel="Check & publish"
        loading={validate.isPending || publish.isPending}
        onConfirm={doPublish}
      />
      <VersionsSheet open={versionsOpen} onOpenChange={setVersionsOpen} workflowId={wf.id} currentId={wf.id} />
    </div>
  );
}
