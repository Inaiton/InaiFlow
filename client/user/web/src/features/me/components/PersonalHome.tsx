"use client";

import { PenLine } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/core/auth/AuthProvider";
import { Avatar, Badge, Button, Card, KeyValue, PageHeader } from "@/components/ui";
import { Invitations } from "./Invitations";
import { JoinRequests } from "./JoinRequests";
import { OrgCards } from "./OrgCards";

/** /me — Personal space home (design: Me-Personal.dc.html). */
export function PersonalHome() {
  const { user, logout } = useAuth();
  if (!user) return null;
  const first = user.full_name.split(" ")[0];
  return (
    <>
      <PageHeader crumbs={[{ label: "Personal space" }]} title={`Welcome back, ${first}`} description="Your profile, security and the organizations you belong to"
        actions={<Button onClick={() => void logout()}>Sign out</Button>} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex min-w-0 flex-col gap-4">
          <OrgCards />
          <Invitations />
          <JoinRequests />
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <Card title="Profile" actions={<Button asChild size="sm"><Link href="/me/security">Edit profile &amp; security</Link></Button>}>
            <div className="flex items-center gap-3">
              <Avatar name={user.full_name} src={user.avatar_url} size={48} />
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[15px] font-semibold text-fg">{user.full_name}</span>
                <span className="truncate text-xs text-fg-muted">{user.email}</span>
              </span>
            </div>
            <KeyValue rows={[
              ["Email", user.is_email_verified ? <Badge tone="success">Verified</Badge> : <Badge tone="warning">Not verified</Badge>],
              ["Mobile", user.mobile ?? "—"],
              ["Two-factor", user.mfa_enabled ? <Badge tone="success">Authenticator app</Badge> : <Badge tone="warning">Off</Badge>],
              ["Professional reg. no.", user.professional_reg_no ?? "—"],
            ]} />
          </Card>
          <Card title="Digital signature" description="Applied when you approve vouchers, SOPs and QC gates"
            actions={<Button asChild size="sm" variant="ghost"><Link href="/me/security#signature"><PenLine /> Replace signature</Link></Button>}>
            <div className="grid h-24 place-items-center rounded-xl border border-dashed border-line-strong bg-canvas">
              {user.signature_url ? (
                // eslint-disable-next-line @next/next/no-img-element -- signed storage URL
                <img src={user.signature_url} alt="Your signature stamp" className="max-h-20 object-contain" />
              ) : (
                <span className="text-[12.5px] text-fg-muted">No signature uploaded yet</span>
              )}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
