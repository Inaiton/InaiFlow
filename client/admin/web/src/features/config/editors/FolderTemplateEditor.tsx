"use client";

import { ArrowDown, ArrowUp, Folder, FolderPlus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { folderListSchema, folderNodeSchema, type FolderNode } from "../schemas";
import { JsonEditor } from "./JsonEditor";
import { countNodes, moveAt, updateAt, type TreePath } from "./tree";
import type { EditorProps } from "./types";

function NodeRow({ node, path, readOnly, onTree }: { node: FolderNode; path: TreePath; readOnly: boolean; onTree: (fn: (l: FolderNode[]) => FolderNode[]) => void }) {
  return (
    <li>
      <div className="group flex items-center gap-1.5 py-1" style={{ paddingLeft: `${(path.length - 1) * 20}px` }}>
        <Folder className="size-4 shrink-0 text-warning" />
        <Input
          className="h-7 max-w-sm text-[13px]"
          value={node.name}
          disabled={readOnly}
          aria-label="Folder name"
          onChange={(e) => onTree((l) => updateAt(l, path, (n) => ({ ...n, name: e.target.value })))}
        />
        {!readOnly ? (
          <span className="flex opacity-60 group-hover:opacity-100">
            <Button variant="ghost" size="icon" aria-label="Add subfolder" onClick={() => onTree((l) => updateAt(l, path, (n) => ({ ...n, children: [...(n.children ?? []), { name: "New folder" }] })))}>
              <FolderPlus />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Move up" onClick={() => onTree((l) => moveAt(l, path, -1))}>
              <ArrowUp />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Move down" onClick={() => onTree((l) => moveAt(l, path, 1))}>
              <ArrowDown />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Remove folder" onClick={() => onTree((l) => updateAt(l, path, () => null))}>
              <Trash2 />
            </Button>
          </span>
        ) : null}
      </div>
      {node.children?.length ? (
        <ul>
          {node.children.map((c, i) => (
            <NodeRow key={i} node={c} path={[...path, i]} readOnly={readOnly} onTree={onTree} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

type Lens = { list: FolderNode[]; wrap: (l: FolderNode[]) => unknown };

/** Accepts `{ subfolders: [...] }` (monthly rule), `{ folders: [...] }`, or a single root node `{ name, children }`. */
function lens(v: unknown): Lens | null {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return null;
  const o = v as Record<string, unknown>;
  for (const k of ["subfolders", "folders"]) {
    const r = folderListSchema.safeParse(o[k]);
    if (r.success) return { list: r.data, wrap: (l) => ({ ...o, [k]: l }) };
  }
  const root = folderNodeSchema.safeParse(o);
  if (root.success) return { list: [root.data], wrap: (l) => l[0] ?? { ...o, children: [] } };
  return null;
}

/** Tree editor for monthly / master-library folder blueprints. */
export function FolderTemplateEditor(props: EditorProps) {
  const x = lens(props.value);
  if (!x) return <JsonEditor {...props} notice="Payload does not match a folder template shape ({ subfolders } / { folders } / { name, children }); editing as JSON." />;
  const single = !("subfolders" in (props.value as object)) && !("folders" in (props.value as object));
  const onTree = (fn: (l: FolderNode[]) => FolderNode[]) => props.onChange(x.wrap(fn(x.list)));
  return (
    <div className="rounded-md border border-line p-3">
      <p className="mb-2 text-xs text-faint">{countNodes(x.list)} folders · system_kind and other keys are preserved.</p>
      <ul>
        {x.list.map((n, i) => (
          <NodeRow key={i} node={n} path={[i]} readOnly={props.readOnly} onTree={onTree} />
        ))}
      </ul>
      {!props.readOnly && !single ? (
        <Button size="sm" variant="ghost" className="mt-2" onClick={() => onTree((l) => [...l, { name: "New folder" }])}>
          <FolderPlus /> Add top-level folder
        </Button>
      ) : null}
    </div>
  );
}
