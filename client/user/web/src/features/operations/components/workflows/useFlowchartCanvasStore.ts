"use client";

import { useSyncExternalStore } from "react";
import { edgeId, newNodeId, SHAPE_LABEL, type Branch, type NodeShape, type WorkflowEdge, type WorkflowGraph, type WorkflowNode } from "../../lib/graph";

/**
 * Small canvas store (skill rule 7): the graph being edited, the selection and a revision
 * counter that drives debounced auto-save. One store per mounted editor.
 */
export interface CanvasState {
  graph: WorkflowGraph;
  selected: { kind: "node" | "edge"; id: string } | null;
  revision: number;
  readOnly: boolean;
}

type Listener = () => void;

export function createCanvasStore(graph: WorkflowGraph, readOnly: boolean) {
  let state: CanvasState = { graph, selected: null, revision: 0, readOnly };
  const listeners = new Set<Listener>();
  const set = (next: Partial<CanvasState>, dirty = true) => {
    state = { ...state, ...next, revision: dirty ? state.revision + 1 : state.revision };
    listeners.forEach((l) => l());
  };
  const editGraph = (fn: (g: WorkflowGraph) => WorkflowGraph) => {
    if (state.readOnly) return;
    set({ graph: fn(state.graph) });
  };
  return {
    get: () => state,
    subscribe: (l: Listener) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    reset: (g: WorkflowGraph, readOnly: boolean) => set({ graph: g, readOnly, selected: null }, false),
    select: (selected: CanvasState["selected"]) => set({ selected }, false),
    addNode: (shape: NodeShape, at?: { x: number; y: number }) => {
      const ids = state.graph.nodes.map((n) => n.id);
      const maxY = state.graph.nodes.reduce((m, n) => Math.max(m, Number(n.position.y)), -120);
      const pos = at ?? { x: 0, y: maxY + 140 };
      const node: WorkflowNode = {
        id: newNodeId(shape, ids), shape, label: SHAPE_LABEL[shape],
        position: { x: String(Math.round(pos.x)), y: String(Math.round(pos.y)) },
        config: shape === "DIAMOND" ? { qc_fields: [], pass_criteria: { mode: "ALL_IN_TOLERANCE" }, reject_action: "SCRAP_NCR" } : shape === "OVAL" ? { trigger: "MANUAL" } : {},
      };
      editGraph((g) => ({ ...g, nodes: [...g.nodes, node] }));
      set({ selected: { kind: "node", id: node.id } }, false);
    },
    updateNode: (id: string, patch: Partial<Omit<WorkflowNode, "id">>) =>
      editGraph((g) => ({ ...g, nodes: g.nodes.map((n) => (n.id === id ? { ...n, ...patch, config: { ...n.config, ...(patch.config ?? {}) } } : n)) })),
    moveNodes: (moves: { id: string; x: number; y: number }[]) =>
      editGraph((g) => ({
        ...g,
        nodes: g.nodes.map((n) => {
          const m = moves.find((mv) => mv.id === n.id);
          return m ? { ...n, position: { x: String(Math.round(m.x)), y: String(Math.round(m.y)) } } : n;
        }),
      })),
    removeNode: (id: string) => {
      editGraph((g) => ({ nodes: g.nodes.filter((n) => n.id !== id), edges: g.edges.filter((e) => e.source !== id && e.target !== id) }));
      set({ selected: null }, false);
    },
    connect: (source: string, target: string) => {
      const src = state.graph.nodes.find((n) => n.id === source);
      const outs = state.graph.edges.filter((e) => e.source === source);
      // Diamond: first connection is PASS, then REJECT, then REWORK.
      const order: Branch[] = src?.shape === "DIAMOND" ? ["PASS", "REJECT", "REWORK"] : ["PASS"];
      const branch = order.find((b) => !outs.some((e) => e.branch === b)) ?? "DEFAULT";
      const id = edgeId(source, target, branch);
      if (source === target || state.graph.edges.some((e) => e.id === id)) return;
      const edge: WorkflowEdge = { id, source, target, branch, label: null };
      editGraph((g) => ({ ...g, edges: [...g.edges, edge] }));
    },
    updateEdge: (id: string, patch: Partial<Pick<WorkflowEdge, "branch" | "label">>) =>
      editGraph((g) => ({ ...g, edges: g.edges.map((e) => (e.id === id ? { ...e, ...patch } : e)) })),
    removeEdge: (id: string) => {
      editGraph((g) => ({ ...g, edges: g.edges.filter((e) => e.id !== id) }));
      set({ selected: null }, false);
    },
  };
}

export type CanvasStore = ReturnType<typeof createCanvasStore>;

export function useFlowchartCanvasStore<T>(store: CanvasStore, pick: (s: CanvasState) => T): T {
  return useSyncExternalStore(store.subscribe, () => pick(store.get()), () => pick(store.get()));
}
