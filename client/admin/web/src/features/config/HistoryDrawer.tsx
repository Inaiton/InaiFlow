"use client";

import { useState } from "react";
import { Dialog, SheetContent } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { JsonDiffView } from "@/components/ui/json-diff-view";
import { EmptyState, QueryState } from "@/components/ui/states";
import { fmtDate, fmtDateTime } from "@/lib/dates";
import { cn } from "@/lib/utils";
import { useConfigHistory } from "./api";

export function HistoryDrawer({ configId, open, onOpenChange }: { configId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const q = useConfigHistory(configId, open);
  const [selected, setSelected] = useState<number | null>(null);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <SheetContent title="Version history" description="Each version shows its diff against the previous one.">
        <QueryState query={q} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No history yet" />}>
          {(raw) => {
            const versions = [...raw].sort((a, b) => b.version - a.version);
            const cur = versions.find((v) => v.version === selected) ?? versions[0]!;
            const prev = versions.find((v) => v.version < cur.version);
            return (
              <div className="grid gap-4 md:grid-cols-[200px_1fr]">
                <ul className="space-y-1">
                  {versions.map((v) => (
                    <li key={v.version}>
                      <button
                        type="button"
                        onClick={() => setSelected(v.version)}
                        className={cn("w-full rounded-md px-2.5 py-2 text-left text-[13px] hover:bg-subtle", v.version === cur.version && "bg-primary-tint")}
                      >
                        <div className="font-medium text-ink">v{v.version}</div>
                        <div className="text-[11px] text-faint">{fmtDateTime(v.created_at)}</div>
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="min-w-0 space-y-3">
                  <div className="flex flex-wrap items-center gap-2 text-[13px]">
                    <Badge tone="accent">v{cur.version}</Badge>
                    <span className="text-muted">by {cur.created_by_name ?? "system"}</span>
                    {cur.effective_from ? <Badge tone="sky">effective {fmtDate(cur.effective_from)}</Badge> : null}
                  </div>
                  {cur.change_reason ? <p className="rounded-md bg-canvas px-3 py-2 text-[13px] text-ink-2">“{cur.change_reason}”</p> : null}
                  <p className="text-xs text-faint">{prev ? `Diff v${prev.version} → v${cur.version}` : "Initial version"}</p>
                  <JsonDiffView before={prev?.payload ?? null} after={cur.payload} />
                </div>
              </div>
            );
          }}
        </QueryState>
      </SheetContent>
    </Dialog>
  );
}
