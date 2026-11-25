"use client";

import "@xyflow/react/dist/style.css";
import { useCallback, useMemo, useState } from "react";
import { Background, Controls, MarkerType, ReactFlow, applyNodeChanges, type Connection, type Edge, type EdgeChange, type NodeChange } from "@xyflow/react";
import { BRANCH_COLOR, SHAPES, defaultConfig, newNodeId, validateGraph, type Graph, type Shape, type WEdge, type WNode } from "./graph";
import { nodeTypes, type FlowNode } from "./nodes";
import { EdgePanel, NodePanel } from "./NodePanel";

type Sel = { kind: "node" | "edge"; id: string } | null;

function toFlowNodes(g: Graph, sel: Sel): FlowNode[] {
  return g.nodes.map((n) => ({
    id: n.id,
    type: "iso",
    position: { x: Number(n.position.x) || 0, y: Number(n.position.y) || 0 },
    data: { label: n.label, shape: n.shape, config: n.config },
    selected: sel?.kind === "node" && sel.id === n.id,
  }));
}

function toFlowEdges(g: Graph, sel: Sel): Edge[] {
  return g.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label || e.branch,
    selected: sel?.kind === "edge" && sel.id === e.id,
    style: { stroke: BRANCH_COLOR[e.branch], strokeWidth: 2 },
    labelStyle: { fill: BRANCH_COLOR[e.branch], fontWeight: 600, fontSize: 11 },
    markerEnd: { type: MarkerType.ArrowClosed, color: BRANCH_COLOR[e.branch] },
  }));
}

const pos = (n: number) => String(Math.round(n));

export default function WorkflowCanvas({ graph, onChange, readOnly }: { graph: Graph; onChange: (g: Graph) => void; readOnly: boolean }) {
  const [sel, setSel] = useState<Sel>(null);
  const nodes = useMemo(() => toFlowNodes(graph, sel), [graph, sel]);
  const edges = useMemo(() => toFlowEdges(graph, sel), [graph, sel]);
  const issues = useMemo(() => validateGraph(graph), [graph]);

  const onNodesChange = useCallback(
    (changes: NodeChange<FlowNode>[]) => {
      const moved = applyNodeChanges(
        changes.filter((c) => c.type === "position" || c.type === "dimensions"),
        nodes,
      );
      if (changes.some((c) => c.type === "position")) {
        const byId = new Map(moved.map((n) => [n.id, n.position]));
        onChange({ ...graph, nodes: graph.nodes.map((n) => { const p = byId.get(n.id); return p ? { ...n, position: { x: pos(p.x), y: pos(p.y) } } : n; }) });
      }
      const removed = changes.filter((c) => c.type === "remove").map((c) => c.id);
      if (removed.length && !readOnly) {
        onChange({ nodes: graph.nodes.filter((n) => !removed.includes(n.id)), edges: graph.edges.filter((e) => !removed.includes(e.source) && !removed.includes(e.target)) });
        setSel(null);
      }
    },
    [graph, nodes, onChange, readOnly],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const removed = changes.filter((c) => c.type === "remove").map((c) => c.id);
      if (removed.length && !readOnly) onChange({ ...graph, edges: graph.edges.filter((e) => !removed.includes(e.id)) });
    },
    [graph, onChange, readOnly],
  );

  const onConnect = useCallback(
    (c: Connection) => {
      if (readOnly || !c.source || !c.target || c.source === c.target) return;
      const src = graph.nodes.find((n) => n.id === c.source);
      const used = graph.edges.filter((e) => e.source === c.source).map((e) => e.branch);
      const branch: WEdge["branch"] = src?.shape === "DIAMOND" ? (["PASS", "REJECT", "REWORK"] as const).find((b) => !used.includes(b)) ?? "DEFAULT" : "PASS";
      const id = `e_${c.source}_${c.target}_${graph.edges.length + 1}`;
      onChange({ ...graph, edges: [...graph.edges, { id, source: c.source, target: c.target, branch, label: null }] });
      setSel({ kind: "edge", id });
    },
    [graph, onChange, readOnly],
  );

  const addNode = (shape: Shape) => {
    const id = newNodeId(graph.nodes, shape);
    const maxY = graph.nodes.reduce((m, n) => Math.max(m, Number(n.position.y) || 0), 0);
    const label = SHAPES.find((s) => s.shape === shape)?.label ?? shape;
    onChange({ ...graph, nodes: [...graph.nodes, { id, shape, label, position: { x: "200", y: pos(graph.nodes.length ? maxY + 140 : 40) }, config: defaultConfig(shape) }] });
    setSel({ kind: "node", id });
  };

  const selNode = sel?.kind === "node" ? graph.nodes.find((n) => n.id === sel.id) : undefined;
  const selEdge = sel?.kind === "edge" ? graph.edges.find((e) => e.id === sel.id) : undefined;
  const updNode = (n: WNode) => onChange({ ...graph, nodes: graph.nodes.map((x) => (x.id === n.id ? n : x)) });
  const updEdge = (e: WEdge) => onChange({ ...graph, edges: graph.edges.map((x) => (x.id === e.id ? e : x)) });

  return (
    <div className="grid gap-3 xl:grid-cols-[1fr_380px]">
      <div className="space-y-2">
        {!readOnly ? (
          <div className="flex flex-wrap gap-1.5">
            {SHAPES.map((s) => (
              <button key={s.shape} type="button" title={s.hint} onClick={() => addNode(s.shape)} className="rounded-md border border-line bg-white px-2.5 py-1.5 text-xs font-medium text-ink-2 hover:bg-subtle">
                + {s.label}
              </button>
            ))}
          </div>
        ) : null}
        <div className="h-[560px] rounded-md border border-line bg-canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, n) => setSel({ kind: "node", id: n.id })}
            onEdgeClick={(_, e) => setSel({ kind: "edge", id: e.id })}
            onPaneClick={() => setSel(null)}
            nodesDraggable={!readOnly}
            nodesConnectable={!readOnly}
            deleteKeyCode={readOnly ? null : ["Delete", "Backspace"]}
            fitView
          >
            <Background gap={16} color="#EAECF0" />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        {issues.length ? (
          <ul className="space-y-0.5 rounded-md bg-warning-tint px-3 py-2 text-xs text-warning-ink">
            {issues.map((i, k) => (
              <li key={k}>• {i.message}</li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-success-ink">Graph structure looks valid.</p>
        )}
      </div>
      <aside className="max-h-[640px] overflow-y-auto rounded-md border border-line bg-white p-3">
        {selNode ? (
          <NodePanel node={selNode} readOnly={readOnly} onChange={updNode} onDelete={() => (onChange({ nodes: graph.nodes.filter((n) => n.id !== selNode.id), edges: graph.edges.filter((e) => e.source !== selNode.id && e.target !== selNode.id) }), setSel(null))} />
        ) : selEdge ? (
          <EdgePanel edge={selEdge} readOnly={readOnly} onChange={updEdge} onDelete={() => (onChange({ ...graph, edges: graph.edges.filter((e) => e.id !== selEdge.id) }), setSel(null))} />
        ) : (
          <p className="text-[13px] text-faint">Select a node or edge to configure it. Drag from a node&apos;s bottom handle to connect; QC gate edges are labelled PASS / REJECT / REWORK.</p>
        )}
      </aside>
    </div>
  );
}
