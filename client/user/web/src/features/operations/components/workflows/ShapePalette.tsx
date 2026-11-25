"use client";

import type { NodeShape } from "../../lib/graph";
import { SHAPE_HINT, SHAPE_LABEL } from "../../lib/graph";

const SHAPES: { shape: NodeShape; icon: string }[] = [
  { shape: "OVAL", icon: "rounded-full" },
  { shape: "RECTANGLE", icon: "rounded-[3px]" },
  { shape: "DIAMOND", icon: "rotate-45 scale-75 rounded-[2px]" },
  { shape: "PARALLEL", icon: "rounded-[3px] outline outline-1 outline-offset-1" },
  { shape: "TERMINATOR", icon: "rounded-full border-2" },
];

/** Toolbar with the five ISO flowchart shapes. */
export function ShapePalette({ onAdd }: { onAdd: (s: NodeShape) => void }) {
  return (
    <div className="absolute top-3 left-3 z-10 flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1 shadow-xs" role="toolbar" aria-label="Add step">
      {SHAPES.map(({ shape, icon }) => (
        <button key={shape} type="button" title={SHAPE_HINT[shape]} onClick={() => onAdd(shape)} className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[12px] font-medium text-fg-2 hover:bg-subtle">
          <span className={`inline-block h-3 w-4 border border-fg-3 ${icon}`} aria-hidden />
          {SHAPE_LABEL[shape]}
        </button>
      ))}
    </div>
  );
}
