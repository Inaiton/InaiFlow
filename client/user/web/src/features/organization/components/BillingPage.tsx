"use client";

import { CreditCard } from "lucide-react";
import { describeError } from "@/core/api/error-messages";
import { formatDate } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { formatBytes } from "@/core/upload";
import { Badge, Card, ErrorState, Hint, IconTile, KeyValue, Meter, PageHeader, Skeleton, StatusBadge, titleCase } from "@/components/ui";
import { useBilling } from "../api-rbac";

/** /o/[slug]/organization/billing (design: Org-Billing.dc.html). Payment gateway is deferred (plan §4). */
export function BillingPage() {
  const { slug } = useOrg();
  const billing = useBilling();
  return (
    <>
      <PageHeader crumbs={[{ label: "Organization", href: `/o/${slug}/organization/profile` }, { label: "Billing" }]} title="Subscription & billing" description="Plan, seats, storage and modules" />
      {billing.isPending ? <Skeleton className="h-72" /> : billing.isError ? <ErrorState message={describeError(billing.error)} onRetry={() => void billing.refetch()} /> : (() => {
        const b = billing.data;
        const gb = b.storage_max_gb * 1024 ** 3;
        return (
          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Current plan" actions={<StatusBadge status={b.org_status} />}>
              <div className="flex items-center gap-3">
                <IconTile icon={CreditCard} tone="violet" size={40} />
                <span className="flex flex-col"><span className="text-lg font-semibold text-ink">{b.plan_name ?? "No plan"}</span><span className="text-xs text-fg-muted">{b.plan_code ?? "—"}</span></span>
              </div>
              <KeyValue rows={[["Trial ends", b.trial_ends_at ? formatDate(b.trial_ends_at) : "—"]]} />
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(b.enabled_modules).map(([m, on]) => <Badge key={m} tone={on ? "success" : "gray"}>{titleCase(m)}{on ? "" : " · not in plan"}</Badge>)}
              </div>
              <Hint tone="gray">To change plan or seats, contact InaiFlow support — online payments arrive soon.</Hint>
            </Card>
            <Card title="Usage">
              <Meter label="Internal seats" value={b.internal_seats_used} max={b.internal_seats_max} detail={`${b.internal_seats_used} of ${b.internal_seats_max}`} />
              <Meter label="External collaborators" value={b.external_seats_used} max={b.external_seats_max} tone="sky" detail={`${b.external_seats_used} of ${b.external_seats_max}`} />
              <Meter label="Document storage" value={b.storage_used_bytes} max={gb} tone="indigo" detail={`${formatBytes(b.storage_used_bytes)} of ${b.storage_max_gb} GB`} />
            </Card>
          </div>
        );
      })()}
    </>
  );
}
