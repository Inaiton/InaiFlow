"use client";

import { Check, Square } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { checkItems, imageData, kvRows, level, qcRows, signatureRoles, tableColumns, tableRows, text, type ReportBlock } from "../../lib/blocks";
import { ImageFromDoc } from "./ImageFromDoc";

/** Read-only rendering of report blocks as React elements (never raw HTML). Looks like an A4 page. */
export function BlockView({ blocks, className, stamps }: { blocks: ReportBlock[]; className?: string; stamps?: Record<string, string | null> }) {
  return (
    <article className={cn("mx-auto flex w-full max-w-[794px] flex-col gap-3 rounded-lg border border-line bg-white px-8 py-8 text-[13px] text-fg shadow-xs", className)}>
      {blocks.length === 0 ? <p className="text-fg-muted">This page is empty.</p> : blocks.map((b) => <div key={b.id}>{renderBlock(b, stamps)}</div>)}
    </article>
  );
}

const cell = "border border-line px-2 py-1.5 text-left align-top";

export function renderBlock(b: ReportBlock, stamps?: Record<string, string | null>): ReactNode {
  switch (b.type) {
    case "heading": {
      const l = level(b);
      const cls = l === 1 ? "text-lg font-bold" : l === 2 ? "text-base font-semibold uppercase tracking-wide" : "text-[13.5px] font-semibold";
      return <p className={cn("m-0", cls)}>{text(b) || " "}</p>;
    }
    case "paragraph":
      return <p className="m-0 whitespace-pre-wrap text-fg-2">{text(b)}</p>;
    case "kv":
      return (
        <table className="w-full border-collapse"><tbody>
          {kvRows(b).map((r, i) => <tr key={i}><th className={cn(cell, "w-1/3 bg-canvas font-medium")}>{r.label}</th><td className={cell}>{r.value}</td></tr>)}
        </tbody></table>
      );
    case "table":
      return (
        <table className="w-full border-collapse">
          <thead><tr>{tableColumns(b).map((c, i) => <th key={i} className={cn(cell, "bg-canvas font-semibold")}>{c}</th>)}</tr></thead>
          <tbody>{tableRows(b).map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={cell}>{c}</td>)}</tr>)}</tbody>
        </table>
      );
    case "qc_table": {
      const rows = qcRows(b);
      if (rows.length === 0) return <p className="m-0 whitespace-pre-wrap text-fg-2">{text(b) || "QC readings appear here once the step is recorded."}</p>;
      return (
        <div className="flex flex-col gap-1">
          <table className="w-full border-collapse">
            <thead><tr>{["#", "Parameter", "Spec", "Observed", "Result"].map((h) => <th key={h} className={cn(cell, "bg-canvas font-semibold")}>{h}</th>)}</tr></thead>
            <tbody>{rows.map((r, i) => (
              <tr key={i}>
                <td className={cell}>{i + 1}</td><td className={cell}>{r.parameter}</td><td className={cell}>{r.spec}</td>
                <td className={cell}>{r.observed}{r.auto ? <span className="ml-1.5 rounded bg-sky-tint px-1 text-[10px] font-semibold text-sky-text">AUTO</span> : null}</td>
                <td className={cn(cell, /fail|out/i.test(r.result) ? "text-danger-text" : /pass/i.test(r.result) ? "text-success-text" : "")}>{r.result}</td>
              </tr>
            ))}</tbody>
          </table>
          {rows.some((r) => r.auto) ? <p className="m-0 text-[11px] text-fg-muted">AUTO = not measured · filled with the nominal spec value (Quick QC).</p> : null}
        </div>
      );
    }
    case "checklist":
      return (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {checkItems(b).map((c, i) => <li key={i} className="flex items-center gap-2">{c.checked ? <Check className="size-4 text-success" /> : <Square className="size-4 text-fg-faint" />}{c.label}</li>)}
        </ul>
      );
    case "signature":
      return (
        <div className="grid gap-4 pt-6" style={{ gridTemplateColumns: `repeat(${Math.max(1, signatureRoles(b).length)}, minmax(0, 1fr))` }}>
          {signatureRoles(b).map((r) => (
            <div key={r} className="flex flex-col gap-1 border-t border-fg-3 pt-1.5 text-[12px]">
              <span className="font-medium">{r}</span>
              {stamps?.[r] ? <span className="text-fg-muted">{stamps[r]}</span> : null}
            </div>
          ))}
        </div>
      );
    case "image": {
      const { documentId, caption } = imageData(b);
      return <figure className="m-0 flex flex-col items-center gap-1">{documentId ? <ImageFromDoc documentId={documentId} alt={caption} /> : <span className="text-fg-faint">No image chosen</span>}{caption ? <figcaption className="text-[11.5px] text-fg-muted">{caption}</figcaption> : null}</figure>;
    }
    case "divider":
      return <hr className="my-1 border-line" />;
    case "page_break":
      return <div className="my-2 border-t-2 border-dashed border-line text-center text-[10px] text-fg-faint">page break</div>;
    default:
      return <p className="m-0 text-fg-muted">{text(b)}</p>;
  }
}
