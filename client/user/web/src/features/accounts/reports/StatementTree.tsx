"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { Schemas } from "@/core/api/types";
import { cn } from "@/lib/utils";
import { Amt } from "../components/Amount";
import { useAccHref } from "../lib/api-base";

type Sec = Schemas["StatementSection"];

function Node({ s, depth, q }: { s: Sec; depth: number; q: string }) {
  const href = useAccHref();
  const [open, setOpen] = useState(depth === 0);
  const kids = s.children.length > 0;
  return (
    <>
      <li className={cn("flex items-center gap-1.5 py-1 pr-3 text-[13px]", depth === 0 ? "font-semibold text-ink" : "text-fg")} style={{ paddingLeft: 8 + depth * 18 }}>
        <button type="button" disabled={!kids} aria-expanded={kids ? open : undefined} aria-label={kids ? `Expand ${s.label}` : undefined} onClick={() => setOpen((o) => !o)} className={cn("size-4 text-fg-muted", !kids && "invisible")}>
          <ChevronRight className={cn("size-4 transition-transform", open && "rotate-90")} />
        </button>
        <span className="flex-1">{s.group_id ? <Link href={href(`/masters/ledgers?group=${s.group_id}&${q}`)} className="text-inherit no-underline hover:underline">{s.label}</Link> : s.label}</span>
        <Amt v={s.amount} className={depth === 0 ? "font-semibold" : ""} />
      </li>
      {open ? s.children.map((c, i) => <Node key={`${c.label}-${i}`} s={c} depth={depth + 1} q={q} />) : null}
    </>
  );
}

/** Collapsible P&L / Balance-sheet / cash-flow sections; group rows drill to the ledgers of that group. */
export function StatementTree({ sections, q = "" }: { sections: Sec[]; q?: string }) {
  if (sections.length === 0) return <p className="px-3 py-2 text-[12.5px] text-fg-muted">Nothing to show.</p>;
  return <ul className="flex flex-col">{sections.map((s, i) => <Node key={`${s.label}-${i}`} s={s} depth={0} q={q} />)}</ul>;
}

export function TotalLine({ label, v, strong }: { label: string; v: string; strong?: boolean }) {
  return <div className={cn("flex justify-between border-t border-line px-3 py-2 text-[13px]", strong && "border-t-2 border-fg font-semibold text-ink")}><span>{label}</span><Amt v={v} strong={strong} /></div>;
}
