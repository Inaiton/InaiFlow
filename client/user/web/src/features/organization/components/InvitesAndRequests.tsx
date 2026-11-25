"use client";

import { Inbox, Mail } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { Schemas } from "@/core/api/types";
import { formatDate, formatDateTime } from "@/core/dates";
import { useCan } from "@/core/permissions/Can";
import { Avatar, Badge, Button, DataTable, EmptyState, Segmented, StatusBadge, type ColumnDef } from "@/components/ui";
import { useDecideJoinRequest, useInvitationAction, useOrgInvitations, useOrgJoinRequests } from "../api";
import { ApproveRequestDialog } from "./MemberDialogs";

type Invitation = Schemas["InvitationOut"];

export function InvitationsTab() {
  const [status, setStatus] = useState<"PENDING" | "all">("PENDING");
  const invites = useOrgInvitations(status === "all" ? undefined : status);
  const action = useInvitationAction();
  const canManage = useCan("organization.members", "FULL");
  const columns: ColumnDef<Invitation, unknown>[] = [
    { accessorKey: "email", header: "Email", cell: ({ getValue }) => <span className="font-medium text-fg">{getValue() as string}</span> },
    { accessorKey: "role_name", header: "Proposed role" },
    { accessorKey: "created_by_name", header: "Invited by", cell: ({ getValue }) => (getValue() as string | null) ?? "—" },
    { accessorKey: "created_at", header: "Sent", cell: ({ getValue }) => formatDate(getValue() as string) },
    { accessorKey: "access_expires_at", header: "Access until", cell: ({ getValue }) => (getValue() ? formatDate(getValue() as string) : "Never") },
    { accessorKey: "status", header: "Status", cell: ({ row: { original: i } }) => <span className="flex flex-col gap-0.5"><StatusBadge status={i.status} />{i.status === "PENDING" ? <span className="text-[11px] text-fg-muted">expires {formatDate(i.expires_at)}</span> : null}</span> },
    {
      id: "actions", header: "", meta: { align: "right" }, cell: ({ row: { original: i } }) =>
        canManage && i.status !== "ACCEPTED" ? (
          <span className="flex justify-end gap-1">
            <Button size="sm" variant="ghost" onClick={() => action.mutate({ id: i.id, action: "resend" }, { onSuccess: () => toast.success(`Invitation re-sent to ${i.email}`) })}>Resend</Button>
            {i.status === "PENDING" ? <Button size="sm" variant="ghost" className="text-danger-text" onClick={() => action.mutate({ id: i.id, action: "revoke" }, { onSuccess: () => toast.success("Invitation revoked") })}>Revoke</Button> : null}
          </span>
        ) : null,
    },
  ];
  return (
    <div className="flex flex-col gap-3">
      <Segmented value={status} onChange={setStatus} aria-label="Invitation status" options={[{ value: "PENDING", label: "Pending" }, { value: "all", label: "All" }]} />
      <DataTable columns={columns} data={invites.data} loading={invites.isPending} aria-label="Invitations"
        empty={<EmptyState icon={Mail} title="No invitations" description="Push invites appear in the person’s personal space for 1-click acceptance." />} />
    </div>
  );
}

export function JoinRequestsTab() {
  const requests = useOrgJoinRequests("PENDING");
  const decide = useDecideJoinRequest();
  const canManage = useCan("organization.members", "FULL");
  const [reviewing, setReviewing] = useState<Schemas["JoinRequestOut"] | null>(null);
  const list = requests.data ?? [];
  if (!requests.isPending && list.length === 0)
    return <EmptyState icon={Inbox} title="No pending join requests" description="People who sign up and enter your workspace code appear here." />;
  return (
    <ul className="flex flex-col gap-2">
      {list.map((r) => (
        <li key={r.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-canvas px-3 py-2.5">
          <Avatar name={r.full_name} tone="teal" size={36} />
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="font-semibold text-fg">{r.full_name}</span>
            <span className="text-xs text-fg-muted">{r.email} · requested {formatDateTime(r.created_at)}</span>
          </span>
          {r.is_email_verified ? <Badge tone="success">Email verified</Badge> : <Badge tone="warning">Unverified</Badge>}
          {r.professional_reg_no ? <Badge tone="sky">Reg. {r.professional_reg_no}</Badge> : null}
          {canManage ? (
            <span className="flex gap-2">
              <Button size="sm" variant="ghost" loading={decide.isPending && decide.variables?.id === r.id && !decide.variables.approve}
                onClick={() => decide.mutate({ id: r.id }, { onSuccess: () => toast.success("Request rejected") })}>Reject</Button>
              <Button size="sm" variant="primary" onClick={() => setReviewing(r)}>Review</Button>
            </span>
          ) : null}
        </li>
      ))}
      {reviewing ? <ApproveRequestDialog request={reviewing} onClose={() => setReviewing(null)} /> : null}
    </ul>
  );
}
