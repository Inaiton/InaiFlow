import { AlertCircle, AlertTriangle } from "lucide-react";
import type { ValidationIssue } from "../../lib/graph";

export function ValidationList({ issues, onPick }: { issues: { errors: ValidationIssue[]; warnings: ValidationIssue[] }; onPick: (nodeId: string) => void }) {
  const row = (i: ValidationIssue, k: string, error: boolean) => (
    <li key={k}>
      <button type="button" disabled={!i.node_id} onClick={() => i.node_id && onPick(i.node_id)} className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left text-[12.5px] hover:bg-subtle disabled:hover:bg-transparent">
        {error ? <AlertCircle className="mt-0.5 size-3.5 flex-none text-danger" aria-hidden /> : <AlertTriangle className="mt-0.5 size-3.5 flex-none text-warning" aria-hidden />}
        <span className="text-fg-2">{i.message}</span>
      </button>
    </li>
  );
  return (
    <section aria-label="Checks" className="flex flex-col gap-1">
      <h3 className="m-0 text-[13px] font-semibold text-fg">{issues.errors.length} to fix · {issues.warnings.length} suggestions</h3>
      <ul className="m-0 flex list-none flex-col p-0">
        {issues.errors.map((i, n) => row(i, `e${n}`, true))}
        {issues.warnings.map((i, n) => row(i, `w${n}`, false))}
      </ul>
    </section>
  );
}
