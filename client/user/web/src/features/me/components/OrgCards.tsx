"use client";

import { ArrowRight, Building2, Plus } from "lucide-react";
import Link from "next/link";
import { describeError } from "@/core/api/error-messages";
import { formatDate } from "@/core/dates";
import type { Schemas } from "@/core/api/types";
import { Avatar, Badge, Button, Card, EmptyState, ErrorState, Skeleton, StatusBadge } from "@/components/ui";
import { useMyOrgs } from "../api";

function OrgRow({ o }: { o: Schemas["MyOrgOut"] }) {
  const active = o.membership_status === "ACTIVE" && o.org_status !== "SUSPENDED" && o.org_status !== "ARCHIVED";
  const body = (
    <>
      <Avatar name={o.mailing_name || o.legal_name} src={o.logo_url} tone="indigo" size={40} />
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-[13.5px] font-semibold text-fg">{o.mailing_name || o.legal_name}</span>
        <span className="text-xs text-fg-muted">{o.public_join_code} · {o.workspace_slug}</span>
      </span>
      <span className="flex flex-wrap items-center justify-end gap-1.5">
        <Badge tone={o.role_code === "ORG_OWNER" ? "accent" : "gray"}>{o.role_name}</Badge>
        {o.is_external ? <Badge tone="sky">External</Badge> : null}
        {o.access_expires_at ? <Badge tone="warning">till {formatDate(o.access_expires_at, "dd MMM")}</Badge> : null}
        {active ? null : <StatusBadge status={o.membership_status !== "ACTIVE" ? o.membership_status : o.org_status} />}
      </span>
      {active ? <ArrowRight className="size-4 text-fg-muted" aria-hidden /> : null}
    </>
  );
  return active ? (
    <Link href={`/o/${o.workspace_slug}`} className="flex items-center gap-3 rounded-xl border border-line bg-canvas px-3 py-2.5 no-underline hover:border-line-strong">{body}</Link>
  ) : (
    <div className="flex items-center gap-3 rounded-xl border border-line bg-canvas px-3 py-2.5 opacity-75">{body}</div>
  );
}

/** Membership list → open an org (design: Me-Personal "My organizations"). */
export function OrgCards() {
  const orgs = useMyOrgs();
  return (
    <Card title="My organizations" description="Switching sets your workspace for every module"
      actions={<Button asChild variant="primary" size="sm"><Link href="/organizations/new"><Plus /> Create organization</Link></Button>}>
      {orgs.isPending ? (
        <div className="flex flex-col gap-2">{[0, 1].map((i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : orgs.isError ? (
        <ErrorState message={describeError(orgs.error)} onRetry={() => void orgs.refetch()} />
      ) : orgs.data.length === 0 ? (
        <EmptyState icon={Building2} tone="indigo" title="You’re not in an organization yet" description="Accept an invitation, request to join with a workspace code, or create your own." />
      ) : (
        <div className="flex flex-col gap-2">{orgs.data.map((o) => <OrgRow key={o.org_id} o={o} />)}</div>
      )}
    </Card>
  );
}
