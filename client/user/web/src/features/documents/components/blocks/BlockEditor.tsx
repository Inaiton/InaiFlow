"use client";

import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import type { Dispatch } from "react";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui";
import { BLOCK_LABELS, emptyBlock, type BlockAction, type BlockType, type ReportBlock } from "../../lib/blocks";
import { ChecklistEditor, HeadingEditor, ImageEditor, KvEditor, ParagraphEditor, SignatureEditor, type EditorProps } from "./SimpleBlockEditors";
import { QcTableEditor, TableEditor } from "./TableBlockEditors";

const EDITORS: Partial<Record<string, (p: EditorProps) => React.ReactNode>> = {
  heading: HeadingEditor, paragraph: ParagraphEditor, kv: KvEditor, table: TableEditor, qc_table: QcTableEditor,
  checklist: ChecklistEditor, signature: SignatureEditor, image: ImageEditor,
};
const ADDABLE: BlockType[] = ["heading", "paragraph", "kv", "qc_table", "table", "checklist", "image", "signature", "divider", "page_break"];

function AddMenu({ dispatch, afterId, label }: { dispatch: Dispatch<BlockAction>; afterId?: string; label?: string }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild><Button size="sm" variant="ghost"><Plus /> {label ?? "Add"}</Button></DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {ADDABLE.map((t) => <DropdownMenuItem key={t} onSelect={() => dispatch({ type: "add", block: emptyBlock(t), afterId })}>{BLOCK_LABELS[t]}</DropdownMenuItem>)}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Structured block editor: inline editing, add / remove / reorder (state via blocksReducer). */
export function BlockEditor({ blocks, dispatch, readOnly }: { blocks: ReportBlock[]; dispatch: Dispatch<BlockAction>; readOnly?: boolean }) {
  return (
    <div className="flex flex-col gap-2">
      {blocks.map((b, i) => {
        const Editor = EDITORS[b.type];
        const label = BLOCK_LABELS[b.type as BlockType] ?? b.type;
        return (
          <section key={b.id} aria-label={label} className="group flex flex-col gap-2 rounded-xl border border-line bg-surface px-3 py-2.5 focus-within:border-primary/50">
            <div className="flex items-center gap-1">
              <span className="flex-1 text-[11px] font-semibold tracking-wide text-fg-muted uppercase">{label}</span>
              {!readOnly ? (
                <span className="flex items-center gap-0.5 opacity-60 group-focus-within:opacity-100 group-hover:opacity-100">
                  <Button size="icon-sm" variant="ghost" aria-label="Move up" disabled={i === 0} onClick={() => dispatch({ type: "move", id: b.id, dir: -1 })}><ArrowUp /></Button>
                  <Button size="icon-sm" variant="ghost" aria-label="Move down" disabled={i === blocks.length - 1} onClick={() => dispatch({ type: "move", id: b.id, dir: 1 })}><ArrowDown /></Button>
                  <Button size="icon-sm" variant="ghost" aria-label={`Remove ${label}`} onClick={() => dispatch({ type: "remove", id: b.id })}><Trash2 /></Button>
                </span>
              ) : null}
            </div>
            {Editor ? (
              <fieldset disabled={readOnly} className="min-w-0"><Editor block={b} onChange={(data) => dispatch({ type: "update", id: b.id, data })} /></fieldset>
            ) : b.type === "divider" ? <hr className="m-0 border-line" /> : <span className="text-xs text-fg-faint">Page break</span>}
            {!readOnly ? <div className="-mb-1 hidden group-focus-within:block group-hover:block"><AddMenu dispatch={dispatch} afterId={b.id} label="Add below" /></div> : null}
          </section>
        );
      })}
      {!readOnly ? <div><AddMenu dispatch={dispatch} label={blocks.length ? "Add block" : "Add the first block"} /></div> : null}
    </div>
  );
}
