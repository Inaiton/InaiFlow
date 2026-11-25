"use client";

import { MoreHorizontal, Search, Users } from "lucide-react";
import { useMemo, useState } from "react";
import type { Schemas } from "@/core/api/types";
import { formatDate } from "@/core/dates";
import { useCan } from "@/core/permissions/Can";
import { describeError } from "@/core/api/error-messages";
import {
  Avatar, Badge, Button, ConfirmDialog, DataTable, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator,
  DropdownMenuTrigger, EmptyState, ErrorState, Input, Segmented, StatusBadge, type ColumnDef,
} from "@/components/ui";
import { useMembers, useRevokeMember, useUpdateMember } from "../api";
import { EditMemberDialog } from "./MemberDialogs";

type Member = Schemas["MemberOut"];
type Filter = "all" | "internal" | "external";

export function MembersTab() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const members = useMembers(q.trim() ? { q: q.trim() } : {});
  const canManage = useCan("organization.members", "FULL");
  const update = useUpdateMember();
  const revoke = useRevokeMember();
  const [editing, setEditing] = useState<Member | null>(null);
  const [revoking, setRevoking] = useState<Member | null>(null);

  const rows = useMemo(
    () => (members.data ?? []).filter((m) => (filter === "all" ? true : filter === "external" ? m.is_external : !m.is_external)),
    [members.data, filter],
  );

  const columns: ColumnDef<Member, unknown>[] = [
    {
      accessorKey: "full_name", header: "Member", cell: ({ row: { original: m } }) => (
        <span className="flex items-center gap-2.5">
          <Avatar name={m.full_name} tone={m.is_external ? "sky" : "indigo"} />
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-semibold text-fg">{m.full_name}</span>
            <span className="truncate text-xs text-fg-muted">{m.email}</span>
          </span>
        </span>
      ),
    },
    { accessorKey: "role_name", header: "Role", cell: ({ row: { original: m } }) => <Badge tone={m.is_owner ? "accent" : "gray"}>{m.is_owner ? "Org owner" : m.role_name}</Badge> },
    { id: "type", header: "Type", cell: ({ row: { original: m } }) => (m.is_external ? <Badge tone="sky">External</Badge> : "Internal") },
    { accessorKey: "access_expires_at", header: "Access until", cell: ({ getValue }) => (getValue() ? formatDate(getValue() as string) : "Never") },
    { accessorKey: "mfa_enabled", header: "2FA", cell: ({ getValue }) => (getValue() ? <Badge tone="success">On</Badge> : <Badge tone="warning">Off</Badge>) },
    { accessorKey: "status", header: "Status", cell: ({ getValue }) => <StatusBadge status={getValue() as string} /> },
    {
      id: "actions", header: "", meta: { align: "right" }, cell: ({ row: { original: m } }) =>
        canManage && !m.is_owner ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button size="icon-sm" variant="ghost" aria-label={`Actions for ${m.full_name}`}><MoreHorizontal /></Button></DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onSelect={() => setEditing(m)}>Change role or expiry</DropdownMenuItem>
              {m.status === "SUSPENDED" ? (
                <DropdownMenuItem onSelect={() => update.mutate({ id: m.membership_id, body: { status: "ACTIVE" } })}>Reactivate</DropdownMenuItem>
              ) : (
                <DropdownMenuItem onSelect={() => update.mutate({ id: m.membership_id, body: { status: "SUSPENDED" } })}>Suspend</DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onSelect={() => setRevoking(m)}>Revoke access</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null,
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Segmented value={filter} onChange={setFilter} aria-label="Member type" options={[{ value: "all", label: "All" }, { value: "internal", label: "Internal" }, { value: "external", label: "External" }]} />
        <div className="flex-1" />
        <Input className="w-full sm:w-72" prefix={<Search className="size-4" />} placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search members" />
      </div>
      {members.isError ? <ErrorState message={describeError(members.error)} onRetry={() => void members.refetch()} /> : (
        <DataTable columns={columns} data={rows} loading={members.isPending} getRowId={(m) => m.membership_id} aria-label="Members"
          empty={<EmptyState icon={Users} title="No members match" description="Try another search or invite someone new." />} />
      )}
      {editing ? <EditMemberDialog member={editing} onClose={() => setEditing(null)} /> : null}
      <ConfirmDialog
        open={revoking !== null}
        onOpenChange={(o) => !o && setRevoking(null)}
        title={`Revoke access for ${revoking?.full_name ?? "member"}?`}
        description="This signs them out everywhere and removes them from the organization. Their vouchers, approvals and audit history stay intact."
        destructive
        confirmLabel="Revoke access"
        loading={revoke.isPending}
        onConfirm={() => { if (revoking) revoke.mutate(revoking.membership_id, { onSuccess: () => setRevoking(null) }); }}
      />
    </div>
  );
}
