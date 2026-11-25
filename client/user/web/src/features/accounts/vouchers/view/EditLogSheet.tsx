"use client";

import { History } from "lucide-react";
import { Badge, EmptyState, JsonDiff, Sheet, SheetContent } from "@/components/ui";
import { formatDateTime } from "@/core/dates";
import { QueryState } from "../../components/QueryState";
import { useEditLog } from "../api";

/** Immutable edit log for one voucher with field-level before/after diffs (MCA/CARO audit trail). */
export function EditLogSheet({ id, number, open, onOpenChange }: { id: string; number: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const log = useEditLog(id, open);
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent title={`Edit log · ${number}`} description="Append-only · cannot be edited or deleted" width={680}>
        <QueryState q={log}>
          {(rows) => rows.length === 0 ? <EmptyState icon={History} title="No alterations yet" description="Creation, edits and cancellation appear here." /> : (
            <ol className="flex flex-col gap-4">
              {rows.map((r) => (
                <li key={r.id} className="flex flex-col gap-2 rounded-xl border border-line p-3">
                  <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
                    <Badge tone={r.action === "CREATE" ? "success" : r.action === "CANCEL" ? "danger" : "indigo"}>{r.action}</Badge>
                    <span className="font-medium text-fg">{r.user_name ?? r.actor_type}</span><span className="text-fg-muted">{r.role_code}</span>
                    <span className="flex-1" /><span className="text-fg-muted tabular">{formatDateTime(r.created_at)}</span>
                  </div>
                  {r.reason ? <p className="text-[12.5px] text-fg-3">Reason: {r.reason}</p> : null}
                  <JsonDiff before={r.before_diff} after={r.after_diff} />
                </li>
              ))}
            </ol>
          )}
        </QueryState>
      </SheetContent>
    </Sheet>
  );
}
