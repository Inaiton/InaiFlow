"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, ConfirmDialog, DataTable, EmptyState, ErrorState, KeyValue, PageHeader, Skeleton, type ColumnDef } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import type { Schemas } from "@/core/api/types";
import { Can } from "@/core/permissions/Can";
import { Amt } from "../components/Amount";
import { PeriodDialog } from "../components/PeriodDialog";
import { QueryState } from "../components/QueryState";
import { useAccHref } from "../lib/api-base";
import { accDate, humanize, inr, qty } from "../lib/format";
import { periodLabel } from "../lib/period";
import { usePeriod } from "../lib/use-period";
import { useRBar } from "../shell/rbar-context";
import { useDeleteStockItem, useItemMovements, useStockItem } from "./api";

type Mv = Schemas["StockMovementOut"];

/** /accounts/inventory/items/[id] — profile, BOM, custom fields and stock movements (drill to voucher). */
export function ItemDetail({ id }: { id: string }) {
  const href = useAccHref();
  const router = useRouter();
  const p = usePeriod();
  const q = useStockItem(id);
  const mv = useItemMovements(id, p.period.from, p.period.to);
  const del = useDeleteStockItem();
  const [remove, setRemove] = useState(false);
  useRBar([{ id: "period", combo: "f2", label: "Period", run: () => p.setDialogOpen(true) }, { id: "alter", combo: "ctrl+e", label: "Alter item", href: href(`/inventory/items/${id}/edit`) }], "accounts");
  if (q.isPending) return <Skeleton className="h-96 w-full" />;
  if (q.isError) return <ErrorState message={describeError(q.error)} onRetry={() => void q.refetch()} />;
  const i = q.data;
  const cf = i.custom_fields && typeof i.custom_fields === "object" && !Array.isArray(i.custom_fields) ? Object.entries(i.custom_fields as Record<string, unknown>) : [];
  const cols: ColumnDef<Mv, unknown>[] = [
    { accessorKey: "date", header: "Date", cell: ({ getValue }) => accDate(getValue() as string) },
    { accessorKey: "voucher_type", header: "Vch type" }, { accessorKey: "voucher_number", header: "Vch no." }, { accessorKey: "godown_name", header: "Godown" },
    { accessorKey: "inward_qty", header: "Inward", meta: { align: "right" }, cell: ({ getValue }) => qty(getValue() as string) },
    { accessorKey: "outward_qty", header: "Outward", meta: { align: "right" }, cell: ({ getValue }) => qty(getValue() as string) },
    { accessorKey: "rate", header: "Rate", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "balance_qty", header: "Balance", meta: { align: "right" }, cell: ({ getValue }) => qty(getValue() as string) },
    { accessorKey: "balance_value", header: "Value", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Stock items", href: href("/inventory/items") }, { label: i.name }]} title={i.name}
        description={`${qty(i.closing_qty)} ${i.uom_primary} · ${inr(i.closing_value)} · ${humanize(i.valuation_method)}`}
        actions={<>
          <Can permission="accounts.inventory_masters" level="FULL"><Button variant="destructive" onClick={() => setRemove(true)}>Delete</Button></Can>
          <Can permission="accounts.inventory_masters" level="WRITE"><Button asChild variant="primary"><Link href={href(`/inventory/items/${id}/edit`)}>Alter item</Link></Button></Can>
        </>} />
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card padded={false} title={`Movements · ${periodLabel(p.period)}`} actions={<Button size="sm" variant="secondary" onClick={() => p.setDialogOpen(true)}>Period (F2)</Button>}>
          <QueryState q={mv}>{(rows) => <DataTable columns={cols} data={rows} getRowId={(r) => `${r.voucher_id}-${r.balance_qty}`} onRowClick={(r) => router.push(href(`/vouchers/${r.voucher_id}`))} aria-label="Stock movements" empty={<EmptyState title="No movements in this period" />} />}</QueryState>
        </Card>
        <div className="flex flex-col gap-4">
          <Card title="Profile">
            <KeyValue rows={[["SKU", i.sku_code ?? "—"], ["Group", i.stock_group_name ?? "Primary"], ["HSN / GST", `${i.hsn_sac_code ?? "—"} · ${Number(i.gst_rate)}%`],
              ["Units", `${i.uom_primary}${i.uom_alternate ? ` · ${i.uom_alternate} (×${i.uom_conversion_factor})` : ""}`], ["Opening", `${qty(i.opening_qty)} @ ${inr(i.opening_rate)}`],
              ["Reorder level", i.reorder_level ? qty(i.reorder_level) : "—"], ...cf.map(([k, v]) => [k, String(v)] as [string, string])]} />
          </Card>
          {i.bom_components.length ? (
            <Card title="Bill of materials">
              <ul className="flex flex-col gap-1 text-[12.5px]">{i.bom_components.map((b) => <li key={b.raw_item_id} className="flex justify-between"><Link href={href(`/inventory/items/${b.raw_item_id}`)}>Component</Link><span className="tabular">{qty(b.qty_per_unit)} / unit · scrap {b.scrap_pct}%</span></li>)}</ul>
            </Card>
          ) : null}
          {i.diagram_url ? <Card title="Drawing"><a href={i.diagram_url} target="_blank" rel="noreferrer noopener">Open drawing</a></Card> : null}
        </div>
      </div>
      <PeriodDialog open={p.dialogOpen} onOpenChange={p.setDialogOpen} period={p.period} fy={p.fy} onApply={p.setPeriod} />
      <ConfirmDialog open={remove} onOpenChange={setRemove} title={`Delete ${i.name}?`} description="Items with stock movements or BOM usage can’t be deleted." destructive confirmLabel="Delete item"
        loading={del.isPending} onConfirm={async () => { await del.mutateAsync(id); router.push(href("/inventory/items")); }} />
    </>
  );
}
