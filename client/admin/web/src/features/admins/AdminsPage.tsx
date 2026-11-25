"use client";

import { useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, NativeSelect } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/misc";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState, QueryState } from "@/components/ui/states";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Forbidden } from "@/components/shell/AppShell";
import { useAuth } from "@/core/auth/AuthProvider";
import { useAdminCan } from "@/core/permissions/Can";
import type { AdminRole } from "@/core/permissions/admin-can";
import { errorMessage } from "@/lib/api/errors";
import { fmtDate, fmtRelative } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";
import { useAdmins, useUpdateAdmin } from "./api";
import { CreateAdminDialog } from "./CreateAdminDialog";

type A = Schemas["AdminAccountOut"];
type Pending = { admin: A; kind: "role" | "deactivate" | "reactivate" } | null;
const col = createColumnHelper<A>();
const ROLES: AdminRole[] = ["SUPERADMIN", "SUPPORT_ADMIN", "BILLING_ADMIN"];

export function AdminsPage() {
  const can = useAdminCan();
  const { admin: me } = useAuth();
  const allowed = can("GET /admin/admins");
  const q = useAdmins(allowed);
  const upd = useUpdateAdmin();
  const [creating, setCreating] = useState(false);
  const [pending, setPending] = useState<Pending>(null);
  const [role, setRole] = useState<AdminRole>("SUPPORT_ADMIN");
  if (!allowed) return <Forbidden />;

  const columns = [
    col.accessor("full_name", {
      header: "Admin",
      cell: (c) => (
        <div>
          <div className="font-medium text-ink">
            {c.getValue()} {c.row.original.id === me?.id ? <span className="text-xs text-faint">(you)</span> : null}
          </div>
          <div className="text-xs text-faint">{c.row.original.email}</div>
        </div>
      ),
    }),
    col.accessor("role", { header: "Role", cell: (c) => <Badge tone={c.getValue() === "SUPERADMIN" ? "accent" : "indigo"}>{c.getValue()}</Badge> }),
    col.accessor("mfa_enabled", { header: "MFA", cell: (c) => (c.getValue() ? <Badge tone="success">Enabled</Badge> : <Badge tone="warning">Pending setup</Badge>) }),
    col.accessor("is_active", { header: "Status", cell: (c) => (c.getValue() ? <Badge tone="success">Active</Badge> : <Badge>Deactivated</Badge>) }),
    col.accessor("last_login_at", { header: "Last login", cell: (c) => fmtRelative(c.getValue()) }),
    col.accessor("created_at", { header: "Created", cell: (c) => fmtDate(c.getValue()) }),
    col.display({
      id: "actions",
      header: "",
      cell: ({ row: { original: a } }) =>
        a.id === me?.id ? null : (
          <div className="flex justify-end gap-1">
            <Button size="sm" onClick={() => (setRole(a.role), setPending({ admin: a, kind: "role" }))}>
              Change role
            </Button>
            {a.is_active ? (
              <Button size="sm" variant="danger-outline" onClick={() => setPending({ admin: a, kind: "deactivate" })}>
                Deactivate
              </Button>
            ) : (
              <Button size="sm" onClick={() => setPending({ admin: a, kind: "reactivate" })}>
                Reactivate
              </Button>
            )}
          </div>
        ),
    }),
  ];

  const confirm = (reason: string) => {
    if (!pending) return;
    const body: Schemas["AdminAccountUpdateIn"] = pending.kind === "role" ? { role, reason } : { is_active: pending.kind === "reactivate", reason };
    upd.mutate({ id: pending.admin.id, body }, { onSuccess: () => (toast.success("Admin updated"), setPending(null)), onError: (e) => toast.error(errorMessage(e)) });
  };

  return (
    <>
      <PageHeader
        title="Platform admins"
        description="Accounts that can sign in to this console (TOTP mandatory)"
        actions={
          can("POST /admin/admins") ? (
            <Button variant="primary" onClick={() => setCreating(true)}>
              <Plus /> New admin
            </Button>
          ) : null
        }
      />
      <Card>
        <QueryState query={q} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No admins" />}>
          {(d) => <DataTable data={d} columns={columns} getRowId={(r) => r.id} />}
        </QueryState>
      </Card>
      {creating ? <CreateAdminDialog onClose={() => setCreating(false)} /> : null}
      {pending ? (
        <ConfirmReasonDialog
          open
          onOpenChange={(o) => !o && setPending(null)}
          title={pending.kind === "role" ? "Change admin role" : pending.kind === "deactivate" ? "Deactivate admin" : "Reactivate admin"}
          description={pending.admin.email}
          destructive={pending.kind === "deactivate"}
          confirmLabel="Confirm"
          pending={upd.isPending}
          extraValid={pending.kind !== "role" || role !== pending.admin.role}
          onConfirm={confirm}
        >
          {pending.kind === "role" ? (
            <Field label="New role">
              <NativeSelect value={role} onChange={(e) => setRole(e.target.value as AdminRole)}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </NativeSelect>
            </Field>
          ) : null}
        </ConfirmReasonDialog>
      ) : null}
    </>
  );
}
