"use client";

import { useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Pencil, Plus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/misc";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState, QueryState } from "@/components/ui/states";
import { useAdminCan } from "@/core/permissions/Can";
import { formatINR } from "@/lib/money";
import type { Schemas } from "@/lib/api/client";
import { usePlans } from "./api";
import { MODULE_FLAGS } from "./schemas";
import { PlanFormDialog } from "./PlanFormDialog";

type Plan = Schemas["PlanOut"];
const col = createColumnHelper<Plan>();

export function PlansPage() {
  const can = useAdminCan();
  const q = usePlans();
  const [editing, setEditing] = useState<Plan | null | "new">(null);
  const canEdit = can("PATCH /admin/plans/{plan_id}");
  const columns = [
    col.accessor("name", {
      header: "Plan",
      cell: (c) => (
        <div>
          <div className="font-medium text-ink">{c.getValue()}</div>
          <div className="font-mono text-[11px] text-faint">{c.row.original.plan_code}</div>
        </div>
      ),
    }),
    col.accessor("monthly_price_inr", { header: "Monthly", cell: (c) => <span className="tabular-nums">{formatINR(c.getValue(), { dp: 0 })}</span> }),
    col.accessor("annual_price_inr", { header: "Annual", cell: (c) => <span className="tabular-nums">{formatINR(c.getValue(), { dp: 0 })}</span> }),
    col.display({ id: "limits", header: "Limits", cell: ({ row: { original: p } }) => <span className="text-[13px]">{p.max_internal_seats} seats · {p.max_external_collaborators} ext · {p.max_storage_gb} GB</span> }),
    col.accessor("enabled_modules", {
      header: "Modules",
      cell: (c) => (
        <div className="flex max-w-xs flex-wrap gap-1">
          {MODULE_FLAGS.filter(([k]) => c.getValue()[k]).map(([k, l]) => (
            <Badge key={k} tone="teal">
              {l}
            </Badge>
          ))}
        </div>
      ),
    }),
    col.accessor("org_count", { header: "Orgs" }),
    col.accessor("is_active", { header: "Status", cell: (c) => (c.getValue() ? <Badge tone="success">Active</Badge> : <Badge>Inactive</Badge>) }),
    col.display({
      id: "edit",
      header: "",
      cell: ({ row }) =>
        canEdit ? (
          <Button size="sm" variant="ghost" onClick={() => setEditing(row.original)} aria-label={`Edit ${row.original.name}`}>
            <Pencil />
          </Button>
        ) : null,
    }),
  ];

  return (
    <>
      <PageHeader
        title="Plans"
        description="Subscription plans, limits and module feature flags"
        actions={
          can("POST /admin/plans") ? (
            <Button variant="primary" onClick={() => setEditing("new")}>
              <Plus /> New plan
            </Button>
          ) : null
        }
      />
      <Card>
        <QueryState query={q} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No plans yet" />}>
          {(plans) => <DataTable data={plans} columns={columns} getRowId={(r) => r.id} />}
        </QueryState>
      </Card>
      {editing ? <PlanFormDialog plan={editing === "new" ? null : editing} onClose={() => setEditing(null)} /> : null}
    </>
  );
}
