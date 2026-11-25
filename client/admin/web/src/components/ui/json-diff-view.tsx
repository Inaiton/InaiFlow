import { diffJson, previewValue } from "@/lib/json-diff";
import { Badge } from "./badge";

export function JsonDiffView({ before, after }: { before: unknown; after: unknown }) {
  const entries = diffJson(before ?? null, after ?? null);
  if (entries.length === 0) return <p className="text-[13px] text-faint">No differences.</p>;
  return (
    <ul className="divide-y divide-line rounded-md border border-line font-mono text-xs">
      {entries.map((e) => (
        <li key={`${e.kind}:${e.path}`} className="grid grid-cols-[72px_1fr] gap-2 px-3 py-2">
          <Badge tone={e.kind === "added" ? "success" : e.kind === "removed" ? "danger" : "warning"}>{e.kind}</Badge>
          <div className="min-w-0 space-y-0.5">
            <div className="font-semibold text-ink-2 break-all">{e.path}</div>
            {e.kind !== "added" ? <div className="break-all text-danger-ink">− {previewValue(e.before)}</div> : null}
            {e.kind !== "removed" ? <div className="break-all text-success-ink">+ {previewValue(e.after)}</div> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function JsonBlock({ value }: { value: unknown }) {
  return <pre className="max-h-96 overflow-auto rounded-md bg-subtle p-3 font-mono text-xs text-ink-2">{JSON.stringify(value, null, 2)}</pre>;
}
