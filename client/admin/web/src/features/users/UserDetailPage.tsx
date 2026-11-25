"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { DefinitionList, PageHeader } from "@/components/ui/misc";
import { EmptyState, QueryState } from "@/components/ui/states";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Forbidden } from "@/components/shell/AppShell";
import { useAdminCan } from "@/core/permissions/Can";
import { errorMessage } from "@/lib/api/errors";
import { fmtDate, fmtDateTime } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";
import { useUser, useUserAction } from "./api";

type Action = Schemas["UserAction"];
const ACTIONS: Record<Action, { label: string; desc: string; destructive: boolean; show: (u: Schemas["AdminUserDetail"]) => boolean }> = {
  VERIFY_EMAIL: { label: "Verify email", desc: "Marks the email as verified without a code.", destructive: false, show: (u) => !u.is_email_verified },
  RESET_MFA: { label: "Reset MFA", desc: "Removes the authenticator and recovery codes. The user must set up MFA again.", destructive: true, show: (u) => u.mfa_enabled },
  REVOKE_SESSIONS: { label: "Revoke sessions", desc: "Signs the user out of every device.", destructive: true, show: (u) => u.active_sessions > 0 },
  UNSUSPEND: { label: "Unsuspend", desc: "Restores the user's ability to sign in.", destructive: false, show: (u) => u.is_suspended },
  SUSPEND: { label: "Suspend user", desc: "Blocks sign-in and revokes all sessions across every organization.", destructive: true, show: (u) => !u.is_suspended },
};

export function UserDetailPage({ id }: { id: string }) {
  const can = useAdminCan();
  const allowed = can("GET /admin/users/{user_id}");
  const q = useUser(id, allowed);
  const m = useUserAction(id);
  const [action, setAction] = useState<Action | null>(null);
  if (!allowed) return <Forbidden />;
  const canAct = can("POST /admin/users/{user_id}/actions");

  return (
    <QueryState query={q}>
      {(u) => (
        <>
          <PageHeader
            crumbs={
              <>
                <Link href="/users" className="hover:underline">
                  Global users
                </Link>{" "}
                / {u.email}
              </>
            }
            title={
              <span className="flex items-center gap-2">
                {u.full_name} {u.is_suspended ? <Badge tone="danger">Suspended</Badge> : null}
              </span>
            }
            description={u.email}
            actions={
              canAct
                ? (Object.keys(ACTIONS) as Action[])
                    .filter((a) => ACTIONS[a].show(u))
                    .map((a) => (
                      <Button key={a} variant={ACTIONS[a].destructive ? "danger-outline" : "secondary"} onClick={() => setAction(a)}>
                        {ACTIONS[a].label}
                      </Button>
                    ))
                : null
            }
          />
          <div className="grid gap-5 lg:grid-cols-3">
            <Card>
              <CardHeader title="Account" />
              <CardBody>
                <DefinitionList
                  items={[
                    ["Email verified", u.is_email_verified ? "Yes" : "No"],
                    ["MFA", u.mfa_enabled ? "Enabled" : "Not enabled"],
                    ["Active sessions", u.active_sessions],
                    ["Mobile", u.mobile ?? "—"],
                    ["Professional reg. no.", u.professional_reg_no ?? "—"],
                    ["Last login", fmtDateTime(u.last_login_at)],
                    ["Joined", fmtDate(u.created_at)],
                  ]}
                />
              </CardBody>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader title="Memberships" description={`${u.memberships.length} organization(s)`} />
              {u.memberships.length === 0 ? (
                <EmptyState title="No memberships" description="Personal space only." />
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Organization</TH>
                      <TH>Role</TH>
                      <TH>Status</TH>
                      <TH>Access expires</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {u.memberships.map((ms) => (
                      <TR key={ms.org_id}>
                        <TD>
                          <Link href={`/organizations/${ms.org_id}`} className="text-primary hover:underline">
                            {ms.org_name}
                          </Link>
                        </TD>
                        <TD className="font-mono text-xs">{ms.role_code}</TD>
                        <TD>
                          <StatusBadge status={ms.status} />
                        </TD>
                        <TD>{fmtDate(ms.access_expires_at)}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </Card>
          </div>
          {action ? (
            <ConfirmReasonDialog
              open
              onOpenChange={(o) => !o && setAction(null)}
              title={ACTIONS[action].label}
              description={`${u.email} — ${ACTIONS[action].desc}`}
              destructive={ACTIONS[action].destructive}
              confirmLabel={ACTIONS[action].label}
              pending={m.isPending}
              onConfirm={(reason) =>
                m.mutate(
                  { action, reason },
                  {
                    onSuccess: () => {
                      toast.success(`${ACTIONS[action].label}: done`);
                      setAction(null);
                    },
                    onError: (e) => toast.error(errorMessage(e)),
                  },
                )
              }
            />
          ) : null}
        </>
      )}
    </QueryState>
  );
}
