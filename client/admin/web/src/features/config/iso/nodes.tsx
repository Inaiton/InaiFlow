"use client";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { cn } from "@/lib/utils";
import type { Shape, WNode } from "./graph";

export type FlowNodeData = { label: string; shape: Shape; config: WNode["config"] };
export type FlowNode = Node<FlowNodeData>;

const handle = "!size-2 !border-white !bg-faint";

function Frame({ shape, selected, children }: { shape: Shape; selected: boolean; children: React.ReactNode }) {
  const ring = selected ? "ring-2 ring-primary ring-offset-2" : "";
  switch (shape) {
    case "OVAL":
      return <div className={cn("flex h-12 w-40 items-center justify-center rounded-[50%] border-2 border-teal bg-teal-tint px-4 text-center", ring)}>{children}</div>;
    case "DIAMOND":
      return (
        <div className={cn("relative flex size-28 items-center justify-center", ring, "rounded-md")}>
          <div className="absolute inset-3 rotate-45 rounded-sm border-2 border-warning bg-warning-tint" />
          <div className="relative max-w-20 text-center">{children}</div>
        </div>
      );
    case "PARALLEL":
      return <div className={cn("w-44 rounded-md border-4 border-double border-violet bg-violet-tint px-3 py-2.5 text-center", ring)}>{children}</div>;
    case "TERMINATOR":
      return <div className={cn("flex h-12 w-40 items-center justify-center rounded-full border-2 border-ink-2 bg-ink-2 px-4 text-center text-white", ring)}>{children}</div>;
    default:
      return <div className={cn("w-44 rounded-md border-2 border-indigo bg-white px-3 py-2.5 text-center", ring)}>{children}</div>;
  }
}

function ShapeNode({ data, selected }: NodeProps<FlowNode>) {
  const qc = data.config.qc_fields?.length ?? 0;
  return (
    <Frame shape={data.shape} selected={!!selected}>
      {data.shape !== "OVAL" ? <Handle type="target" position={Position.Top} className={handle} /> : null}
      <div className="text-[12px] font-semibold leading-tight">{data.label || "Untitled"}</div>
      {qc ? <div className="mt-0.5 text-[10px] opacity-70">{qc} QC field{qc > 1 ? "s" : ""}</div> : null}
      {data.config.assigned_role_code && data.shape === "RECTANGLE" ? <div className="text-[10px] text-faint">{data.config.assigned_role_code}</div> : null}
      {data.shape !== "TERMINATOR" ? <Handle type="source" position={Position.Bottom} className={handle} /> : null}
      {data.shape === "DIAMOND" ? (
        <>
          <Handle id="right" type="source" position={Position.Right} className={handle} />
          <Handle id="left" type="source" position={Position.Left} className={handle} />
        </>
      ) : null}
    </Frame>
  );
}

export const nodeTypes = { iso: ShapeNode };
