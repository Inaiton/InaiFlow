"use client";

import Link from "next/link";
import { Badge, Sheet, SheetContent, Skeleton } from "@/components/ui";
import { formatDate } from "@/core/dates";
import { useWorkflowVersions } from "../../api/workflows";
import { useOpsPath } from "../../paths";

export function VersionsSheet({ open, onOpenChange, workflowId, currentId }: { open: boolean; onOpenChange: (o: boolean) => void; workflowId: string; currentId: string }) {
  const p = useOpsPath();
  const versions = useWorkflowVersions(workflowId, open);
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent title="Versions" description="Published versions are frozen; runs keep the version they started with." width={420}>
        {!versions.data ? <Skeleton className="h-40" /> : (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {versions.data.map((v) => (
              <li key={v.id}>
                <Link href={p(`/workflows/${v.id}`)} onClick={() => onOpenChange(false)} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5 no-underline hover:border-line-strong" aria-current={v.id === currentId ? "page" : undefined}>
                  <span className="flex flex-1 flex-col">
                    <span className="text-[13px] font-semibold text-fg">v{v.version}{v.id === currentId ? " · viewing" : ""}</span>
                    <span className="text-xs text-fg-muted">{v.published_at ? `Published ${formatDate(v.published_at)}` : `Created ${formatDate(v.created_at)}`} · {v.active_run_count} active run(s)</span>
                  </span>
                  <Badge tone={v.status === "PUBLISHED" ? "success" : v.status === "DRAFT" ? "indigo" : "gray"}>{v.status === "PUBLISHED" ? "Published" : v.status === "DRAFT" ? "Draft" : "Archived"}</Badge>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SheetContent>
    </Sheet>
  );
}
