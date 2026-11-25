"use client";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { AlertCircle, Lock } from "lucide-react";
import type { Schemas } from "@/core/api/types";
import { cn } from "@/lib/utils";
import type { WorkflowNode } from "../../lib/graph";
import { STEP_LABEL } from "./status";

type StepStatus = Schemas["StepStatus"];

export interface FlowNodeData extends Record<string, unknown> {
  node: WorkflowNode;
  status?: StepStatus;
  detail?: string;
  issues?: string[];
  locked?: boolean;
}
export type FlowRfNode = Node<FlowNodeData, "iso">;

const STATUS_CLASS: Record<StepStatus, string> = {
  PENDING: "border-line bg-surface text-fg-muted",
  ACTIVE: "border-sky bg-sky-tint text-fg ring-2 ring-sky/25",
  PASSED: "border-success bg-success-tint text-fg",
  REJECTED: "border-danger bg-danger-tint text-fg",
  SKIPPED: "border-violet bg-violet-tint text-fg",
  LOCKED: "border-teal bg-teal-tint text-fg",
};

const SHAPE_CLASS: Record<WorkflowNode["shape"], string> = {
  OVAL: "rounded-full px-6",
  RECTANGLE: "rounded-lg",
  DIAMOND: "rounded-lg",
  PARALLEL: "rounded-lg outline outline-2 outline-offset-[3px]",
  TERMINATOR: "rounded-full border-[3px] px-6",
};

/** One custom node renders all five ISO flowchart shapes (diamond = rotated square backdrop). */
export function IsoNode({ data, selected }: NodeProps<FlowRfNode>) {
  const { node, status, detail, issues, locked } = data;
  const tone = status ? STATUS_CLASS[status] : "border-line-strong bg-surface text-fg";
  const hasIssues = (issues?.length ?? 0) > 0;
  const body = (
    <div className="flex min-w-0 flex-col items-center gap-0.5 text-center">
      <span className="max-w-[170px] truncate text-[12.5px] font-semibold">{node.label || "Untitled"}</span>
      {detail ? <span className="max-w-[170px] truncate text-[11px] text-fg-muted">{detail}</span> : null}
      {status ? <span className="text-[10.5px] font-medium uppercase tracking-wide text-fg-3">{STEP_LABEL[status]}</span> : null}
    </div>
  );
  return (
    <div className="relative" title={hasIssues ? issues!.join("\n") : node.label}>
      <Handle type="target" position={Position.Top} className="!size-2 !border-0 !bg-fg-muted" />
      {node.shape === "DIAMOND" ? (
        <div className="relative grid h-[96px] w-[180px] place-items-center">
          <div className={cn("absolute size-[68px] rotate-45 rounded-md border-2", tone, selected && "!border-primary", hasIssues && "!border-danger")} aria-hidden />
          <div className={cn("relative z-10 rounded-md border px-2 py-1", tone, selected && "!border-primary")}>{body}</div>
        </div>
      ) : (
        <div className={cn("min-w-[170px] border-2 px-3 py-2", SHAPE_CLASS[node.shape], tone, selected && "!border-primary", hasIssues && "!border-danger", node.shape === "PARALLEL" && "outline-current/30")}>
          {body}
        </div>
      )}
      {hasIssues ? <AlertCircle className="absolute -top-2 -right-2 size-4 rounded-full bg-surface text-danger" aria-label={`${issues!.length} issue(s)`} /> : null}
      {locked ? <Lock className="absolute -top-2 -left-2 size-4 rounded-full bg-surface p-0.5 text-teal-text" aria-label="Signed off" /> : null}
      <Handle type="source" position={Position.Bottom} className="!size-2 !border-0 !bg-fg-muted" />
    </div>
  );
}

export const nodeTypes = { iso: IsoNode };

export const BRANCH_COLOR: Record<Schemas["Branch"], string> = {
  PASS: "#12B76A", REJECT: "#F04438", REWORK: "#F79009", DEFAULT: "#667085",
};
