"use client";

import { useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { NativeSelect } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/misc";
import { DataTable } from "@/components/ui/data-table";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, QueryState } from "@/components/ui/states";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Forbidden } from "@/components/shell/AppShell";
import { useAdminCan } from "@/core/permissions/Can";
import { errorMessage } from "@/lib/api/errors";
import { fmtDate, fmtDateTime } from "@/lib/dates";
import { formatINR } from "@/lib/money";
import type { Schemas } from "@/lib/api/client";
import { useInvoices, useSetInvoiceStatus, type InvoiceFilters } from "./api";
import { CreateInvoiceDialog } from "./CreateInvoiceDialog";
import { OrgPicker } from "./OrgPicker";

type Inv = Schemas["SubscriptionInvoiceOut"];
const col = createColumnHelper<Inv>();

export function BillingPage() {
  const can = useAdminCan();
  const allowed = can("GET /admin/billing/invoices");
  const [f, setF] = useState<InvoiceFilters>({ limit: 25, offset: 0 });
  const [org, setOrg] = useState<{ id: string; name: string } | null>(null);
  const [creating, setCreating] = useState(false);
  const [action, setAction] = useState<{ inv: Inv; status: "PAID" | "VOID" } | null>(null);
  const list = useInvoices(f, allowed);
  const setStatus = useSetInvoiceStatus();
  if (!allowed) return <Forbidden />;
  const canPatch = can("PATCH /admin/billing/invoices/{invoice_id}");
  const set = (p: Partial<InvoiceFilters>) => setF((x) => ({ ...x, ...p, offset: p.offset ?? 0 }));

  const columns = [
    col.accessor("invoice_number", { header: "Invoice", cell: (c) => <span className="font-mono text-[13px]">{c.getValue()}</span> }),
    col.accessor("org_name", { header: "Organization" }),
    col.display({ id: "period", header: "Period", cell: ({ row: { original: i } }) => `${fmtDate(i.period_start)} – ${fmtDate(i.period_end)}` }),
    col.accessor("amount_inr", { header: "Amount", cell: (c) => <span className="tabular-nums">{formatINR(c.getValue())}</span> }),
    col.accessor("status", { header: "Status", cell: (c) => <StatusBadge status={c.getValue()} /> }),
    col.accessor("paid_at", { header: "Paid", cell: (c) => fmtDateTime(c.getValue()) }),
    col.display({
      id: "actions",
      header: "",
      cell: ({ row: { original: i } }) =>
        canPatch && i.status === "DUE" ? (
          <div className="flex justify-end gap-1">
            <Button size="sm" onClick={() => setAction({ inv: i, status: "PAID" })}>
              Mark paid
            </Button>
            <Button size="sm" variant="danger-outline" onClick={() => setAction({ inv: i, status: "VOID" })}>
              Void
            </Button>
          </div>
        ) : null,
    }),
  ];

  return (
    <>
      <PageHeader
        title="Billing"
        description="Manual subscription invoices (payment gateway is deferred)"
        actions={
          can("POST /admin/billing/invoices") ? (
            <Button variant="primary" onClick={() => setCreating(true)}>
              <Plus /> Create invoice
            </Button>
          ) : null
        }
      />
      <Card>
        <div className="flex flex-wrap items-start gap-2 border-b border-line p-3">
          <div className="w-80">
            <OrgPicker value={org} onChange={(o) => (setOrg(o), set({ org_id: o?.id }))} />
          </div>
          <NativeSelect className="w-40" value={f.status ?? ""} onChange={(e) => set({ status: e.target.value })} aria-label="Status filter">
            <option value="">All statuses</option>
            <option value="DUE">Due</option>
            <option value="PAID">Paid</option>
            <option value="VOID">Void</option>
          </NativeSelect>
        </div>
        <QueryState query={list} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="No invoices" />}>
          {(d) => (
            <>
              <DataTable data={d.items} columns={columns} getRowId={(r) => r.id} />
              <Pagination total={d.total} limit={d.limit} offset={d.offset} onChange={(offset) => set({ offset })} />
            </>
          )}
        </QueryState>
      </Card>
      {creating ? <CreateInvoiceDialog onClose={() => setCreating(false)} /> : null}
      {action ? (
        <ConfirmReasonDialog
          open
          onOpenChange={(o) => !o && setAction(null)}
          title={action.status === "PAID" ? "Mark invoice paid" : "Void invoice"}
          description={`${action.inv.invoice_number} · ${action.inv.org_name} · ${formatINR(action.inv.amount_inr)}`}
          destructive={action.status === "VOID"}
          confirmLabel={action.status === "PAID" ? "Mark paid" : "Void invoice"}
          pending={setStatus.isPending}
          onConfirm={(reason) =>
            setStatus.mutate(
              { id: action.inv.id, status: action.status, reason },
              { onSuccess: () => (toast.success("Invoice updated"), setAction(null)), onError: (e) => toast.error(errorMessage(e)) },
            )
          }
        />
      ) : null}
    </>
  );
}
