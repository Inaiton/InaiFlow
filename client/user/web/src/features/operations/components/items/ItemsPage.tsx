"use client";

import { Package, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Badge, Button, Card, DataTable, EmptyState, ErrorState, Input, PageHeader, Segmented, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { formatMoney, formatQty } from "@/core/money";
import { Can } from "@/core/permissions/Can";
import { useOpsItems } from "../../api/items";
import { useOpsPath } from "../../paths";

type Item = Schemas["OpsItemOut"];
const LIMIT = 25;

/** /operations/items — what you make and the workflow it follows. */
export function ItemsPage() {
  const p = useOpsPath();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<"ALL" | "STOCK_ITEM" | "STANDALONE_PROCESS">("ALL");
  const [offset, setOffset] = useState(0);
  const items = useOpsItems({ q: q || undefined, target_type: kind === "ALL" ? undefined : kind, limit: LIMIT, offset });
  const columns = useMemo<ColumnDef<Item, unknown>[]>(() => [
    {
      header: "Item", accessorKey: "name",
      cell: ({ row }) => (
        <span className="flex flex-col">
          <span className="font-semibold text-fg">{row.original.name}</span>
          <span className="text-xs text-fg-muted">{row.original.sku_code ?? "No code"} · {row.original.uom_primary}</span>
        </span>
      ),
    },
    { header: "Kind", cell: ({ row }) => <Badge tone={row.original.target_type === "STANDALONE_PROCESS" ? "violet" : "sky"}>{row.original.target_type === "STANDALONE_PROCESS" ? "Process" : "Stock item"}</Badge> },
    { header: "Workflows", accessorKey: "workflow_count", meta: { align: "right" } },
    { header: "Runs", cell: ({ row }) => `${row.original.stats.run_count}${row.original.stats.active_run_count ? ` · ${row.original.stats.active_run_count} active` : ""}`, meta: { align: "right" } },
    { header: "Avg yield", cell: ({ row }) => (row.original.stats.avg_yield_pct ? `${formatQty(row.original.stats.avg_yield_pct, 1)}%` : "—"), meta: { align: "right" } },
    { header: "Avg unit cost", cell: ({ row }) => (row.original.stats.avg_unit_cost ? formatMoney(row.original.stats.avg_unit_cost) : "—"), meta: { align: "right" } },
  ], []);
  const newBtn = (
    <Can permission="operations.items" level="WRITE">
      <Button asChild variant="primary"><Link href={p("/items/new")}><Plus /> New item</Link></Button>
    </Can>
  );
  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Operations", href: p() }, { label: "Items" }]} title="Items & processes" description="What you make, its drawing and the workflow it follows" actions={newBtn} />
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <Input className="max-w-xs" prefix={<Search className="size-4" />} placeholder="Search items" value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} aria-label="Search items" />
          <Segmented aria-label="Kind" value={kind} onChange={(v) => { setKind(v); setOffset(0); }} options={[{ value: "ALL", label: "All" }, { value: "STOCK_ITEM", label: "Stock items" }, { value: "STANDALONE_PROCESS", label: "Processes" }]} />
        </div>
        {items.isError ? <ErrorState message={describeError(items.error)} onRetry={() => void items.refetch()} /> : (
          <DataTable
            aria-label="Items"
            columns={columns}
            data={items.data?.items}
            loading={items.isPending}
            getRowId={(r) => r.id}
            onRowClick={(r) => router.push(p(`/items/${r.id}`))}
            pagination={items.data ? { total: items.data.total, limit: LIMIT, offset, onOffsetChange: setOffset } : undefined}
            empty={<EmptyState icon={Package} tone="indigo" title={q ? "No items match" : "Add your first item"} description="An item is the part or process a workflow produces." action={q ? undefined : newBtn} />}
          />
        )}
      </Card>
    </div>
  );
}
