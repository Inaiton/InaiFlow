"use client";

import { Package } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Card, DataTable, DatePicker, EmptyState, Field, NativeSelect, PageHeader, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { sum } from "@/core/money";
import { Amt } from "../components/Amount";
import { QueryState } from "../components/QueryState";
import { GodownSelect } from "../components/Selects";
import { INVENTORY_NAV, SubNav } from "../components/SubNav";
import { useAccHref } from "../lib/api-base";
import { humanize, qty } from "../lib/format";
import { ExportButtons } from "../reports/ReportFrame";
import { useStockGroups, useStockSummary } from "./api";

type Row = Schemas["StockSummaryRow"];

/** /accounts/inventory — stock summary by item with valuation (design: Acc-Inventory / Acc-Rep-Stock). */
export function StockSummaryPage() {
  const href = useAccHref();
  const router = useRouter();
  const [asOf, setAsOf] = useState<string | null>(null);
  const [godown, setGodown] = useState("");
  const [group, setGroup] = useState("");
  const groups = useStockGroups();
  const q = useStockSummary({ ...(asOf ? { as_of: asOf } : {}), ...(godown ? { godown_id: godown } : {}), ...(group ? { stock_group_id: group } : {}) });
  const cols: ColumnDef<Row, unknown>[] = [
    { accessorKey: "name", header: "Stock item", cell: ({ row: { original: r } }) => <span className="font-medium text-fg">{r.name}</span> },
    { accessorKey: "stock_group_name", header: "Group", cell: ({ getValue }) => (getValue() as string | null) ?? "—" },
    { accessorKey: "valuation_method", header: "Valuation", cell: ({ getValue }) => humanize(getValue() as string) },
    { id: "qty", header: "Closing qty", meta: { align: "right" }, cell: ({ row: { original: r } }) => <span className="tabular">{qty(r.quantity)} {r.uom}</span> },
    { accessorKey: "rate", header: "Rate", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "value", header: "Value", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { id: "re", header: "Reorder", cell: ({ row: { original: r } }) => (r.below_reorder ? <Badge tone="warning">Below reorder</Badge> : r.reorder_level ? <Badge tone="success">OK</Badge> : null) },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Inventory" }]} title="Stock summary" description="Closing quantity and value by item"
        actions={<ExportButtons report="stock-summary" query={asOf ? { as_of: asOf } : {}} />} />
      <SubNav items={INVENTORY_NAV} />
      <Card padded={false}>
        <div className="grid grid-cols-1 gap-3 border-b border-line p-4 md:grid-cols-3">
          <Field label="As on"><DatePicker value={asOf} onValueChange={setAsOf} /></Field>
          <Field label="Godown"><GodownSelect value={godown} onValueChange={setGodown} placeholder="All godowns" /></Field>
          <Field label="Stock group"><NativeSelect value={group} onChange={(e) => setGroup(e.target.value)}><option value="">All groups</option>{(groups.data ?? []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</NativeSelect></Field>
        </div>
        <QueryState q={q}>
          {(rows) => (
            <>
              <DataTable columns={cols} data={rows} getRowId={(r) => r.stock_item_id} onRowClick={(r) => router.push(href(`/inventory/items/${r.stock_item_id}`))} aria-label="Stock summary"
                empty={<EmptyState icon={Package} title="No stock yet" description="Create stock items with opening stock, or post a purchase." />} />
              <div className="flex justify-end gap-2 border-t-2 border-fg px-4 py-2 text-[13px] font-semibold">Grand total <Amt strong v={sum(rows.map((r) => r.value))} /></div>
            </>
          )}
        </QueryState>
      </Card>
    </>
  );
}
