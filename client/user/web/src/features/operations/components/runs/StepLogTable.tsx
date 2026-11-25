"use client";

import { DataTable, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { formatDateTime } from "@/core/dates";
import { formatQty } from "@/core/money";
import { SHAPE_LABEL } from "../../lib/graph";
import { StepStatusBadge } from "../shared/status";

type Step = Schemas["StepOut"];

const cols: ColumnDef<Step, unknown>[] = [
  { header: "#", cell: ({ row }) => row.original.sequence + 1 },
  { header: "Step", accessorKey: "step_name", cell: ({ row }) => <span className="font-medium text-fg">{row.original.step_name}</span> },
  { header: "Shape", cell: ({ row }) => SHAPE_LABEL[row.original.node_shape] },
  { header: "Status", cell: ({ row }) => <StepStatusBadge status={row.original.status} /> },
  { header: "In", cell: ({ row }) => formatQty(row.original.input_qty), meta: { align: "right" } },
  { header: "OK", cell: ({ row }) => formatQty(row.original.accepted_qty), meta: { align: "right" } },
  { header: "Rej", cell: ({ row }) => formatQty(row.original.rejected_qty), meta: { align: "right" } },
  { header: "Recorded", cell: ({ row }) => (row.original.executed_at ? `${row.original.executed_by_name ?? ""} · ${formatDateTime(row.original.executed_at)}` : "—") },
  { header: "Signed off", cell: ({ row }) => (row.original.signed_off_at ? row.original.signed_off_by_name : "—") },
];

/** Timestamps, counts and sign-offs — goes into the dossier. */
export function StepLogTable({ steps, onPick }: { steps: Step[]; onPick: (s: Step) => void }) {
  return <DataTable aria-label="Step log" columns={cols} data={[...steps].sort((a, b) => a.sequence - b.sequence)} getRowId={(s) => s.id} onRowClick={onPick} minWidth={760} />;
}
