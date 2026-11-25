"use client";

import { useRouter } from "next/navigation";
import { FileText } from "lucide-react";
import { DataTable, EmptyState, StatusBadge, type ColumnDef } from "@/components/ui";
import { Amt } from "../components/Amount";
import { useAccHref } from "../lib/api-base";
import { accDate } from "../lib/format";
import type { VoucherSummary } from "../vouchers/api";

export function voucherColumns(): ColumnDef<VoucherSummary, unknown>[] {
  return [
    { accessorKey: "voucher_date", header: "Date", cell: ({ getValue }) => <span className="tabular whitespace-nowrap">{accDate(getValue() as string)}</span> },
    { id: "particulars", header: "Particulars", cell: ({ row: { original: v } }) => <span className="flex flex-col"><span className="font-medium text-fg">{v.party_name ?? v.narration ?? "—"}</span>{v.party_name && v.narration ? <span className="truncate text-[11.5px] text-fg-muted">{v.narration}</span> : null}</span> },
    { accessorKey: "voucher_type_name", header: "Vch type" },
    { accessorKey: "voucher_number", header: "Vch no.", cell: ({ getValue }) => <span className="tabular">{getValue() as string}</span> },
    { accessorKey: "status", header: "Status", cell: ({ getValue }) => <StatusBadge status={getValue() as string} /> },
    { accessorKey: "total_amount", header: "Amount", meta: { align: "right" }, cell: ({ row: { original: v } }) => <Amt v={v.total_amount} className={v.status === "CANCELLED" ? "line-through text-fg-muted" : ""} /> },
  ];
}

/** Voucher register table; rows drill into the printable voucher. */
export function VoucherTable({ data, loading, pagination, empty }: { data: VoucherSummary[] | undefined; loading?: boolean; pagination?: { total: number; limit: number; offset: number; onOffsetChange: (o: number) => void }; empty?: React.ReactNode }) {
  const router = useRouter();
  const href = useAccHref();
  return (
    <DataTable columns={voucherColumns()} data={data} loading={loading} pagination={pagination} getRowId={(v) => v.id} onRowClick={(v) => router.push(href(`/vouchers/${v.id}`))}
      empty={empty ?? <EmptyState icon={FileText} title="No vouchers" description="Press F8 for a sales invoice or F9 for a purchase." />} aria-label="Vouchers" />
  );
}
