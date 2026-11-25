"use client";

import { Copy, KeyRound, Lock, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import type { PermissionMap } from "@/core/permissions/levels";
import { Badge, Button, Card, ConfirmDialog, ErrorState, Hint, PageHeader, Skeleton } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useDeleteRole, usePermissionKeys, useRoles, useUpdateRole } from "../api-rbac";
import { PermissionMatrix } from "./PermissionMatrix";
import { CreateRoleDialog } from "./RoleDialogs";

function RoleEditor({ role, canEdit, onClone, onDeleted }: { role: Schemas["RoleOut"]; canEdit: boolean; onClone: () => void; onDeleted: () => void }) {
  const keys = usePermissionKeys();
  const update = useUpdateRole();
  const del = useDeleteRole();
  const [draft, setDraft] = useState<PermissionMap | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const isOwner = role.role_code === "ORG_OWNER";
  const readOnly = !canEdit || role.is_system_role;
  const value = draft ?? role.permissions;
  return (
    <Card
      title={<span className="flex items-center gap-2">{role.role_name} <span className="font-normal text-fg-muted">· permission matrix</span></span>}
      description="None hides the feature and blocks the API · Full allows approve, lock and delete"
      actions={
        <>
          {canEdit && !isOwner ? <Button size="sm" onClick={onClone}><Copy /> Clone as custom</Button> : null}
          {canEdit && !role.is_system_role ? (
            <>
              <Button size="sm" variant="destructive" onClick={() => setConfirmDelete(true)}><Trash2 /> Delete</Button>
              <Button size="sm" variant="primary" disabled={!draft} loading={update.isPending}
                onClick={() => draft && update.mutate({ id: role.id, body: { permissions: draft } }, { onSuccess: () => setDraft(null) })}>Save</Button>
            </>
          ) : null}
        </>
      }
    >
      {isOwner ? <Hint tone="accent" title="Org owner">Always has full control everywhere. This role can’t be edited.</Hint> : role.is_system_role ? (
        <Hint tone="gray">System roles are read-only. Clone one as a custom role to change its access.</Hint>
      ) : null}
      {keys.isPending ? <Skeleton className="h-80" /> : keys.isError ? <ErrorState message={describeError(keys.error)} onRetry={() => void keys.refetch()} /> : (
        <PermissionMatrix modules={keys.data} value={isOwner ? Object.fromEntries(keys.data.flatMap((m) => m.keys.map((k) => [k.key, "FULL" as const]))) : value} onChange={setDraft} readOnly={readOnly || isOwner} />
      )}
      <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} destructive title={`Delete role “${role.role_name}”?`}
        description={role.member_count > 0 ? `${role.member_count} member(s) still use this role — move them first.` : "This can’t be undone."}
        confirmLabel="Delete role" loading={del.isPending} onConfirm={() => del.mutate(role.id, { onSuccess: () => { setConfirmDelete(false); onDeleted(); } })} />
    </Card>
  );
}

/** /o/[slug]/organization/roles (design: Org-Roles.dc.html). */
export function RolesPage() {
  const { slug } = useOrg();
  const roles = useRoles();
  const canEdit = useCan("organization.roles_rbac", "FULL");
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState<{ from?: string } | null>(null);
  const list = roles.data ?? [];
  const role = list.find((r) => r.id === selected) ?? list[0];
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Organization", href: `/o/${slug}/organization/profile` }, { label: "Roles & access" }]}
        title="Roles & permissions"
        description="Three layers: access level · sub-module matrix · record overrides"
        actions={<>
          <Button asChild><Link href={`/o/${slug}/organization/acl`}><Lock /> Record overrides</Link></Button>
          {canEdit ? <Button variant="primary" onClick={() => setCreating({})}><Plus /> New custom role</Button> : null}
        </>}
      />
      {roles.isError ? <ErrorState message={describeError(roles.error)} onRetry={() => void roles.refetch()} /> : (
        <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <Card title="Roles" description={`${list.filter((r) => r.is_system_role).length} system · ${list.filter((r) => !r.is_system_role).length} custom`}>
            {roles.isPending ? <Skeleton className="h-60" /> : (
              <ul className="flex flex-col gap-1" role="listbox" aria-label="Roles">
                {list.map((r) => (
                  <li key={r.id}>
                    <button type="button" role="option" aria-selected={role?.id === r.id} onClick={() => setSelected(r.id)}
                      className={cn("flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left", role?.id === r.id ? "bg-primary-tint" : "hover:bg-canvas")}>
                      <KeyRound className={cn("size-4", role?.id === r.id ? "text-primary" : "text-fg-muted")} aria-hidden />
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate text-[13px] font-semibold text-fg">{r.role_name}</span>
                        <span className="text-[11.5px] text-fg-muted">{r.is_system_role ? "System" : "Custom"}{r.is_external_collaborator ? " · external" : ""}</span>
                      </span>
                      <Badge>{r.member_count}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {role ? <RoleEditor key={role.id} role={role} canEdit={canEdit} onClone={() => setCreating({ from: role.id })} onDeleted={() => setSelected(null)} /> : roles.isPending ? <Skeleton className="h-96" /> : null}
        </div>
      )}
      {creating ? <CreateRoleDialog roles={list} initialFrom={creating.from} onClose={() => setCreating(null)} onCreated={(id) => { setCreating(null); setSelected(id); }} /> : null}
    </>
  );
}
