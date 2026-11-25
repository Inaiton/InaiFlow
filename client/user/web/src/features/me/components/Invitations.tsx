"use client";

import { Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { formatDate } from "@/core/dates";
import { Avatar, Button, Card, Skeleton } from "@/components/ui";
import { useAcceptInvitation, useDeclineInvitation, useInvitations } from "../api";

/** Pending push invitations, 1-click accept (design: Me-Invite-Accept). Hidden when there are none. */
export function Invitations({ alwaysShow = false }: { alwaysShow?: boolean }) {
  const invites = useInvitations();
  const accept = useAcceptInvitation();
  const decline = useDeclineInvitation();
  const router = useRouter();
  const list = invites.data ?? [];
  if (!alwaysShow && !invites.isPending && list.length === 0) return null;
  return (
    <Card title="Invitations" description="Organizations that invited you" id="invitations">
      {invites.isPending ? <Skeleton className="h-16" /> : list.length === 0 ? (
        <p className="text-[13px] text-fg-muted">No pending invitations.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {list.map((i) => (
            <li key={i.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-canvas px-3 py-2.5">
              <Avatar name={i.org_name} tone="violet" size={36} />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13.5px] font-semibold text-fg">{i.org_name}</span>
                <span className="text-xs text-fg-muted">
                  Invited as {i.role_name}{i.invited_by_name ? ` by ${i.invited_by_name}` : ""} · expires {formatDate(i.expires_at)}
                  {i.access_expires_at ? ` · access until ${formatDate(i.access_expires_at)}` : ""}
                </span>
              </span>
              <span className="flex gap-2">
                <Button size="sm" variant="ghost" loading={decline.isPending && decline.variables === i.id} onClick={() => decline.mutate(i.id)}>Decline</Button>
                <Button size="sm" variant="primary" loading={accept.isPending && accept.variables === i.id}
                  onClick={() => accept.mutate(i.id, { onSuccess: (org) => router.push(`/o/${org.workspace_slug}`) })}>
                  <Mail /> Accept &amp; open
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
