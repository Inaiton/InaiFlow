"use client";

import { Package } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, DataTable, EmptyState, ErrorState, Field, Input, NativeSelect, PageHeader, type ColumnDef } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { Can } from "@/core/permissions/Can";
import { Amt } from "../components/Amount";
import { INVENTORY_NAV, SubNav } from "../components/SubNav";
import { useAccHref } from "../lib/api-base";
import { humanize, qty } from "../lib/format";
import { useDebouncedValue } from "../lib/hooks";
import { useRBar } from "../shell/rbar-context";
import { useStockGroups, useStockItems, type StockItem } from "./api";

/** /accounts/inventory/items */
export function ItemsPage() {
  const href = useAccHref();
  const router = useRouter();
  const [text, setText] = useState("");
  const [group, setGroup] = useState("");
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(text, 250);
  const groups = useStockGroups();
  const list = useStockItems({ limit: 50, offset, ...(q ? { q } : {}), ...(group ? { stock_group_id: group } : {}) });
  useRBar([{ id: "create", combo: "alt+c", label: "Create item", href: href("/inventory/items/new") }], "accounts");
  const cols: ColumnDef<StockItem, unknown>[] = [
    { accessorKey: "name", header: "Stock item", cell: ({ row: { original: i } }) => <span className="flex items-center gap-2 font-medium text-fg">{i.name}{i.target_type === "STANDALONE_PROCESS" ? <Badge tone="violet">Process</Badge> : null}</span> },
    { accessorKey: "sku_code", header: "SKU", cell: ({ getValue }) => (getValue() as string | null) ?? "—" },
    { accessorKey: "hsn_sac_code", header: "HSN", cell: ({ getValue }) => (getValue() as string | null) ?? "—" },
    { accessorKey: "gst_rate", header: "GST", cell: ({ getValue }) => `${Number(getValue() as string)}%` },
    { accessorKey: "valuation_method", header: "Valuation", cell: ({ getValue }) => humanize(getValue() as string) },
    { id: "qty", header: "Closing qty", meta: { align: "right" }, cell: ({ row: { original: i } }) => <span className="tabular">{qty(i.closing_qty)} {i.uom_primary}</span> },
    { accessorKey: "closing_value", header: "Value", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Inventory", href: href("/inventory") }, { label: "Stock items" }]} title="Stock items" description="Synced with Operations items"
        actions={<Can permission="accounts.inventory_masters" level="WRITE"><Button asChild variant="primary"><Link href={href("/inventory/items/new")}>New item (Alt C)</Link></Button></Can>} />
      <SubNav items={INVENTORY_NAV} />
      <Card padded={false}>
        <div className="grid grid-cols-1 gap-3 border-b border-line p-4 md:grid-cols-[minmax(0,1fr)_260px]">
          <Field label="Search"><Input autoFocus value={text} onChange={(e) => { setOffset(0); setText(e.target.value); }} placeholder="Name, SKU, HSN…" /></Field>
          <Field label="Stock group"><NativeSelect value={group} onChange={(e) => { setOffset(0); setGroup(e.target.value); }}><option value="">All groups</option>{(groups.data ?? []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</NativeSelect></Field>
        </div>
        {list.isError ? <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} /> : (
          <DataTable columns={cols} data={list.data?.items} loading={list.isPending} getRowId={(i) => i.id} onRowClick={(i) => router.push(href(`/inventory/items/${i.id}`))} aria-label="Stock items"
            pagination={list.data ? { total: list.data.total, limit: list.data.limit, offset: list.data.offset, onOffsetChange: setOffset } : undefined}
            empty={<EmptyState icon={Package} title="No stock items" description="Create one with Alt C." />} />
        )}
      </Card>
    </>
  );
}
