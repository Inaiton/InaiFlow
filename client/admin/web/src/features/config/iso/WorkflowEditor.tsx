"use client";

import dynamic from "next/dynamic";
import { Field, Input, Textarea } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/states";
import { JsonEditor } from "../editors/JsonEditor";
import type { EditorProps } from "../editors/types";
import { extractGraph } from "./graph";

const WorkflowCanvas = dynamic(() => import("./WorkflowCanvas"), { ssr: false, loading: () => <LoadingState rows={6} /> });

export function WorkflowEditor(props: EditorProps) {
  const x = extractGraph(props.value);
  if (!x) return <JsonEditor {...props} notice="Payload is not a workflow graph ({ nodes, edges } or { graph_definition }); editing as JSON." />;
  const meta = x.meta;
  const setMeta = (k: string, v: string) => props.onChange({ ...meta, [k]: v || null });
  return (
    <div className="space-y-4">
      {meta ? (
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Template name">
            <Input value={String(meta.name ?? "")} disabled={props.readOnly} onChange={(e) => setMeta("name", e.target.value)} />
          </Field>
          <Field label="ISO clause">
            <Input value={String(meta.iso_clause_ref ?? "")} disabled={props.readOnly} onChange={(e) => setMeta("iso_clause_ref", e.target.value)} placeholder="8.5.1" />
          </Field>
          <Field label="Description" className="md:col-span-3">
            <Textarea className="min-h-12" value={String(meta.description ?? "")} disabled={props.readOnly} onChange={(e) => setMeta("description", e.target.value)} />
          </Field>
        </div>
      ) : null}
      <WorkflowCanvas graph={x.graph} readOnly={props.readOnly} onChange={(g) => props.onChange(x.wrap(g))} />
    </div>
  );
}
