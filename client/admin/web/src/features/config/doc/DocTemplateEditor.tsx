"use client";

import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/input";
import { JsonEditor } from "../editors/JsonEditor";
import type { EditorProps } from "../editors/types";
import { BLOCK_LABEL, BLOCK_TYPES, canonicalType, defaultData, extractBlocks, newBlockId, type Block, type BlockType } from "./blocks";
import { BlockForm, insertToken } from "./BlockForm";
import { TokenPicker } from "./TokenPicker";

const TOKEN_TYPES = new Set(["heading", "paragraph", "kv", "qc_table", "checklist"]);

/** Block-list editor for report templates. Blocks are structured JSON (rendered as React elements, never HTML). */
export function DocTemplateEditor(props: EditorProps) {
  const x = extractBlocks(props.value);
  if (!x) return <JsonEditor {...props} notice="Payload is not a block template ({ blocks } or { content_schema: { blocks } }); editing as JSON." />;
  const { blocks } = x;
  const ro = props.readOnly;
  const set = (b: Block[]) => props.onChange(x.wrap(b));
  const upd = (i: number, data: Record<string, unknown>) => set(blocks.map((b, j) => (j === i ? { ...b, data } : b)));
  const move = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= blocks.length) return;
    const c = blocks.slice();
    [c[i], c[j]] = [c[j]!, c[i]!];
    set(c);
  };

  return (
    <div className="space-y-2">
      {blocks.map((b, i) => (
        <div key={b.id} className="rounded-md border border-line bg-white">
          <div className="flex items-center gap-1 border-b border-line bg-canvas px-3 py-1.5">
            <span className="text-xs font-semibold text-muted">{BLOCK_LABEL[canonicalType(b.type) as BlockType] ?? b.type}</span>
            <span className="font-mono text-[11px] text-faint">#{b.id}</span>
            {!ro ? (
              <span className="ml-auto flex items-center">
                {TOKEN_TYPES.has(canonicalType(b.type)) ? <TokenPicker onPick={(t) => upd(i, insertToken(b, t))} /> : null}
                <Button variant="ghost" size="icon" aria-label="Move up" onClick={() => move(i, -1)}>
                  <ArrowUp />
                </Button>
                <Button variant="ghost" size="icon" aria-label="Move down" onClick={() => move(i, 1)}>
                  <ArrowDown />
                </Button>
                <Button variant="ghost" size="icon" aria-label="Remove block" onClick={() => set(blocks.filter((_, j) => j !== i))}>
                  <Trash2 />
                </Button>
              </span>
            ) : null}
          </div>
          <div className="p-3">
            <BlockForm block={b} readOnly={ro} onChange={(d) => upd(i, d)} />
          </div>
        </div>
      ))}
      {blocks.length === 0 ? <p className="rounded-md border border-dashed border-line py-6 text-center text-[13px] text-faint">No blocks yet.</p> : null}
      {!ro ? (
        <NativeSelect
          className="w-56"
          value=""
          aria-label="Add block"
          onChange={(e) => {
            const t = e.target.value as BlockType;
            if (t) set([...blocks, { id: newBlockId(blocks), type: t, data: defaultData(t) }]);
          }}
        >
          <option value="">+ Add block…</option>
          {BLOCK_TYPES.map((t) => (
            <option key={t} value={t}>
              {BLOCK_LABEL[t]}
            </option>
          ))}
        </NativeSelect>
      ) : null}
    </div>
  );
}
