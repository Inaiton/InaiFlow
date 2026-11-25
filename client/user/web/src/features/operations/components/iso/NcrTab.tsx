"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Button, DataTable, DecimalInput, Dialog, DialogContent, EmptyState, ErrorState, Field, NativeSelect, Textarea, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { formatDate } from "@/core/dates";
import { formatQty } from "@/core/money";
import { Can } from "@/core/permissions/Can";
import { useCreateNcr, useNcrs } from "../../api/iso";
import { useOpsPath } from "../../paths";
import { NCR_STATUSES, NcrBadge } from "../shared/status";

type Ncr = Schemas["NcrOut"];
const LIMIT = 25;

export function NcrTab() {
  const p = useOpsPath();
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(false);
  const list = useNcrs({ status: status || undefined, limit: LIMIT, offset });
  const cols = useMemo<ColumnDef<Ncr, unknown>[]>(() => [
    { header: "NCR", accessorKey: "ncr_number", cell: ({ row }) => <span className="font-semibold text-fg">{row.original.ncr_number}</span> },
    { header: "Where", cell: ({ row }) => <span className="text-xs">{row.original.run_title ?? "Manual"}{row.original.step_name ? ` · ${row.original.step_name}` : ""}</span> },
    { header: "Defect", cell: ({ row }) => <span className="line-clamp-1 max-w-72">{row.original.defect_description}</span> },
    { header: "Qty", cell: ({ row }) => formatQty(row.original.rejected_qty), meta: { align: "right" } },
    { header: "Owner", cell: ({ row }) => row.original.assigned_to_name ?? "—" },
    { header: "Raised", cell: ({ row }) => formatDate(row.original.created_at) },
    { header: "Status", cell: ({ row }) => <NcrBadge status={row.original.status} /> },
  ], []);
  return (
    <div className="flex flex-col gap-3 pt-2">
      <div className="flex flex-wrap items-center gap-2">
        <NativeSelect className="w-48" aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
          <option value="">All statuses</option>
          {NCR_STATUSES.map((s) => <option key={s} value={s}>{s === "VERIFIED_CLOSED" ? "Closed" : s.charAt(0) + s.slice(1).toLowerCase()}</option>)}
        </NativeSelect>
        <span className="flex-1" />
        <Can permission="operations.iso_compliance" level="WRITE"><Button onClick={() => setOpen(true)}><Plus /> Raise NCR</Button></Can>
      </div>
      {list.isError ? <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} /> : (
        <DataTable aria-label="NCRs" columns={cols} data={list.data?.items} loading={list.isPending} getRowId={(n) => n.id}
          onRowClick={(n) => router.push(p(`/iso-compliance/ncr/${n.id}`))}
          pagination={list.data ? { total: list.data.total, limit: LIMIT, offset, onOffsetChange: setOffset } : undefined}
          empty={<EmptyState title="No NCRs" description="Rejected units at a QC gate raise an NCR automatically." />} />
      )}
      <NewNcrDialog open={open} onOpenChange={setOpen} />
    </div>
  );
}

function NewNcrDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const create = useCreateNcr();
  const [qty, setQty] = useState<string | null>(null);
  const [defect, setDefect] = useState("");
  const submit = async () => {
    await create.mutateAsync({ rejected_qty: qty ?? "0", defect_description: defect.trim() });
    setQty(null); setDefect("");
    onOpenChange(false);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Raise an NCR" description="For problems found outside a run — customer complaints, audits, supplier issues."
        footer={<><Button onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="primary" disabled={defect.trim().length < 3} loading={create.isPending} onClick={() => void submit()}>Raise NCR</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Field label="What is wrong?" required><Textarea value={defect} onChange={(e) => setDefect(e.target.value)} /></Field>
          <Field label="Affected quantity"><DecimalInput kind="qty" decimals={4} value={qty} onValueChange={setQty} /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}
