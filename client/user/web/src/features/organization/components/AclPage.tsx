"use client";

import { Lock, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import type { Schemas } from "@/core/api/types";
import { formatDate } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import { LEVEL_LABEL } from "@/core/permissions/levels";
import { Badge, Button, Card, DataTable, EmptyState, ErrorState, PageHeader, type ColumnDef } from "@/components/ui";
import { useAcl, useDeleteAcl } from "../api-rbac";
import { AclDialog } from "./AclDialog";
import { RESOURCE_TYPES } from "./resource-lookup";

type Acl = Schemas["AclOut"];
const typeLabel = (t: string) => RESOURCE_TYPES.find((r) => r.value === t)?.label ?? t;

/** /o/[slug]/organization/acl — record-level ACL overrides (design: Org-ACL-New.dc.html). */
export function AclPage() {
  const { slug } = useOrg();
  const acl = useAcl();
  const del = useDeleteAcl();
  const canEdit = useCan("organization.roles_rbac", "FULL");
  const [open, setOpen] = useState(false);
  const columns: ColumnDef<Acl, unknown>[] = [
    { accessorKey: "subject_name", header: "Applies to", cell: ({ row: { original: a } }) => <span className="flex items-center gap-2 font-semibold text-fg">{a.subject_name}<Badge>{a.subject_type === "USER" ? "Member" : "Role"}</Badge></span> },
    { accessorKey: "resource_type", header: "Resource", cell: ({ getValue }) => typeLabel(getValue() as string) },
    { accessorKey: "resource_name", header: "Record", cell: ({ getValue }) => <span className="font-medium text-fg">{getValue() as string}</span> },
    { accessorKey: "access_level", header: "Access", cell: ({ getValue }) => <Badge tone={getValue() === "NONE" ? "danger" : getValue() === "FULL" ? "accent" : "indigo"}>{LEVEL_LABEL[getValue() as Acl["access_level"]]}</Badge> },
    { accessorKey: "created_at", header: "Added", cell: ({ getValue }) => formatDate(getValue() as string) },
    {
      id: "x", header: "", meta: { align: "right" }, cell: ({ row: { original: a } }) =>
        canEdit ? <Button size="icon-sm" variant="ghost" aria-label="Remove override" loading={del.isPending && del.variables === a.id} onClick={() => del.mutate(a.id)}><Trash2 /></Button> : null,
    },
  ];
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Organization", href: `/o/${slug}/organization/profile` }, { label: "Roles & access", href: `/o/${slug}/organization/roles` }, { label: "Record overrides" }]}
        title="Record-level overrides"
        description="Narrow or extend a role for specific stock items, runs, folders or godowns. A member override wins over a role override."
        actions={canEdit ? <Button variant="primary" onClick={() => setOpen(true)}><Plus /> Add override</Button> : null}
      />
      <Card>
        {acl.isError ? <ErrorState message={describeError(acl.error)} onRetry={() => void acl.refetch()} /> : (
          <DataTable columns={columns} data={acl.data} loading={acl.isPending} aria-label="Record overrides"
            empty={<EmptyState icon={Lock} title="No overrides yet" description="E.g. let an external auditor read only Component 1 runs without seeing payroll or margins." />} />
        )}
      </Card>
      {open ? <AclDialog onClose={() => setOpen(false)} /> : null}
    </>
  );
}
