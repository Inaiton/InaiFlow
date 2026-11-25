"use client";

import { Plus, Search, Workflow } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { formatDate } from "@/core/dates";
import { Can } from "@/core/permissions/Can";
import { useWorkflowLibrary, useWorkflows } from "../../api/workflows";
import { useOpsPath } from "../../paths";

/** /operations/workflows — your workflows + the ISO template library (design Ops-WF-Templates). */
export function WorkflowsPage() {
  const p = useOpsPath();
  const [q, setQ] = useState("");
  const list = useWorkflows({ q: q || undefined });
  const lib = useWorkflowLibrary();
  const newBtn = <Can permission="operations.workflows" level="WRITE"><Button asChild variant="primary"><Link href={p("/workflows/new")}><Plus /> New workflow</Link></Button></Can>;
  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Operations", href: p() }, { label: "Workflow studio" }]} title="Workflow studio" description="Steps and QC gates for each item, versioned for ISO 9001" actions={newBtn} />
      <Card title="Your workflows" actions={<Input className="w-60" prefix={<Search className="size-4" />} placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search workflows" />}>
        {list.isError ? <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} /> : !list.data ? <Skeleton className="h-32" /> : list.data.length === 0 ? (
          <EmptyState icon={Workflow} tone="indigo" title="No workflows yet" description="Start from an ISO template below — most shops only change step names and tolerances." action={newBtn} />
        ) : (
          <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 xl:grid-cols-3">
            {list.data.map((w) => (
              <li key={w.id}>
                <Link href={p(`/workflows/${w.id}`)} className="flex h-full flex-col gap-2 rounded-xl border border-line px-4 py-3 no-underline hover:border-line-strong">
                  <span className="flex items-center gap-2">
                    <span className="flex-1 truncate text-[13.5px] font-semibold text-fg">{w.name}</span>
                    <Badge tone={w.status === "PUBLISHED" ? "success" : "indigo"}>v{w.version} · {w.status === "PUBLISHED" ? "Published" : "Draft"}</Badge>
                  </span>
                  <span className="text-xs text-fg-muted">{w.stock_item_name ?? "No item linked"}{w.iso_clause_ref ? ` · ISO ${w.iso_clause_ref}` : ""}</span>
                  <span className="text-xs text-fg-muted">{w.node_count} steps · {w.active_run_count} active runs · {w.published_at ? `published ${formatDate(w.published_at)}` : `created ${formatDate(w.created_at)}`}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="ISO 9001 templates" description="Pre-built flows using all five ISO shapes">
        {!lib.data ? <Skeleton className="h-24" /> : (
          <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 xl:grid-cols-3">
            {lib.data.map((t) => (
              <li key={t.key} className="flex flex-col gap-1.5 rounded-xl border border-line bg-canvas px-4 py-3">
                <span className="text-[13.5px] font-semibold text-fg">{t.name}</span>
                <span className="text-xs text-fg-muted">{t.description}</span>
                <span className="text-xs text-fg-muted">{t.graph_definition.nodes.length} steps{t.iso_clause_ref ? ` · clause ${t.iso_clause_ref}` : ""}</span>
                <Can permission="operations.workflows" level="WRITE">
                  <Button asChild size="sm" className="self-start"><Link href={p(`/workflows/new?template=${encodeURIComponent(t.key)}`)}>Use template</Link></Button>
                </Can>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
