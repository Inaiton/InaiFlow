"use client";

import "@xyflow/react/dist/style.css";
import {
  Background, Controls, MarkerType, ReactFlow, applyNodeChanges, type Connection, type Edge, type EdgeChange, type NodeChange,
} from "@xyflow/react";
import { useMemo, useState } from "react";
import type { WorkflowGraph } from "../../lib/graph";
import { BRANCH_COLOR, nodeTypes, type FlowNodeData, type FlowRfNode } from "./FlowNodes";

export interface FlowCanvasProps {
  graph: WorkflowGraph;
  readOnly?: boolean;
  selectedId?: string | null;
  /** Per-node extras (run status, counts, validation issues). */
  decorate?: (nodeId: string) => Omit<FlowNodeData, "node">;
  /** Edge id → units taken (run view). Taken edges are animated and thick; others are faded. */
  taken?: Map<string, string>;
  onSelect?: (sel: { kind: "node" | "edge"; id: string } | null) => void;
  onMove?: (moves: { id: string; x: number; y: number }[]) => void;
  onConnect?: (source: string, target: string) => void;
  onRemoveEdge?: (id: string) => void;
  onRemoveNode?: (id: string) => void;
  className?: string;
}

const toRf = (g: WorkflowGraph, prev: FlowRfNode[], selectedId: string | null | undefined, decorate?: FlowCanvasProps["decorate"]): FlowRfNode[] => {
  const byId = new Map(prev.map((n) => [n.id, n]));
  return g.nodes.map((n) => {
    const old = byId.get(n.id);
    return {
      ...(old ?? {}),
      id: n.id,
      type: "iso",
      position: old?.dragging ? old.position : { x: Number(n.position.x), y: Number(n.position.y) },
      selected: n.id === selectedId,
      data: { node: n, ...(decorate?.(n.id) ?? {}) },
    };
  });
};

/** @xyflow/react canvas shared by the workflow studio (editable) and the run pipeline (read-only). */
export default function FlowCanvas({ graph, readOnly, selectedId, decorate, taken, onSelect, onMove, onConnect, onRemoveEdge, onRemoveNode, className }: FlowCanvasProps) {
  const [nodes, setNodes] = useState<FlowRfNode[]>(() => toRf(graph, [], selectedId, decorate));
  // Re-derive nodes when inputs change (adjust-state-during-render; keeps xyflow's measured sizes).
  const [src, setSrc] = useState({ graph, selectedId, decorate });
  if (src.graph !== graph || src.selectedId !== selectedId || src.decorate !== decorate) {
    setSrc({ graph, selectedId, decorate });
    setNodes((prev) => toRf(graph, prev, selectedId, decorate));
  }

  const edges = useMemo<Edge[]>(() => graph.edges.map((e) => {
    const qty = taken?.get(e.id);
    const isTaken = qty !== undefined;
    const color = BRANCH_COLOR[e.branch];
    const faded = taken && !isTaken;
    return {
      id: e.id, source: e.source, target: e.target, selected: e.id === selectedId,
      label: `${e.label || e.branch}${isTaken ? ` · ${qty}` : ""}`,
      animated: isTaken,
      style: { stroke: color, strokeWidth: isTaken ? 3 : 1.6, opacity: faded ? 0.35 : 1, strokeDasharray: e.branch === "REWORK" ? "6 4" : undefined },
      labelStyle: { fill: color, fontWeight: 600, fontSize: 11 },
      labelBgStyle: { fill: "#fff" },
      markerEnd: { type: MarkerType.ArrowClosed, color },
    };
  }), [graph.edges, taken, selectedId]);

  const onNodesChange = (changes: NodeChange<FlowRfNode>[]) => {
    const allowed = readOnly ? changes.filter((c) => c.type === "dimensions" || c.type === "select") : changes;
    setNodes((nds) => applyNodeChanges(allowed, nds));
    for (const c of allowed) if (c.type === "remove") onRemoveNode?.(c.id);
  };
  const onEdgesChange = (changes: EdgeChange[]) => {
    if (readOnly) return;
    for (const c of changes) if (c.type === "remove") onRemoveEdge?.(c.id);
  };

  return (
    <div className={className ?? "h-full w-full"}>
      <ReactFlow<FlowRfNode, Edge>
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={(c: Connection) => { if (!readOnly && c.source && c.target) onConnect?.(c.source, c.target); }}
        onNodeClick={(_, n) => onSelect?.({ kind: "node", id: n.id })}
        onEdgeClick={(_, e) => onSelect?.({ kind: "edge", id: e.id })}
        onPaneClick={() => onSelect?.(null)}
        onNodeDragStop={(_, __, dragged) => onMove?.(dragged.map((n) => ({ id: n.id, x: n.position.x, y: n.position.y })))}
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        deleteKeyCode={readOnly ? null : ["Backspace", "Delete"]}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.1 }}
        minZoom={0.2}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} color="#EAECF0" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

