"use client";

import { describeError } from "@/core/api/error-messages";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import { Card, ErrorState, KeyValue, PageHeader, Skeleton } from "@/components/ui";
import { ImageUploadCard } from "@/features/me/components/ImageUploadCard";
import { useOrgProfile, useUploadOrgFile } from "../api";
import { BranchesCard } from "./BranchesCard";
import { OrgProfileForm } from "./OrgProfileForm";
import { TransferOwnershipButton } from "./TransferOwnership";

/** /o/[slug]/organization/profile (design: Org-Profile.dc.html). */
export function OrgProfilePage() {
  const { slug, context } = useOrg();
  const profile = useOrgProfile();
  const canEdit = useCan("organization.profile", "FULL");
  const logo = useUploadOrgFile("LOGO");
  const stamp = useUploadOrgFile("STAMP");
  return (
    <>
      <PageHeader crumbs={[{ label: "Organization", href: `/o/${slug}/organization/profile` }, { label: "Profile" }]} title="Organization profile" description="Statutory identity used across invoices, returns and reports" />
      {profile.isPending ? <Skeleton className="h-96" /> : profile.isError ? <ErrorState message={describeError(profile.error)} onRetry={() => void profile.refetch()} /> : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,1fr)]">
          <div className="flex min-w-0 flex-col gap-4">
            <OrgProfileForm org={profile.data} />
            <BranchesCard />
          </div>
          <div className="flex min-w-0 flex-col gap-4">
            <ImageUploadCard title="Company logo" description="Used on invoices & reports" imageUrl={profile.data.logo_url} placeholder={<span className="text-[12.5px] text-fg-muted">No logo</span>}
              hint="PNG · up to 2 MB" uploading={logo.isPending} disabled={!canEdit} onFile={(f) => logo.mutate(f)} />
            <ImageUploadCard title="Digital stamp" description="Stamped on approvals" imageUrl={profile.data.stamp_url} placeholder={<span className="text-[12.5px] text-fg-muted">No stamp</span>}
              hint="Transparent PNG" uploading={stamp.isPending} disabled={!canEdit} onFile={(f) => stamp.mutate(f)} />
            <Card title="Ownership" actions={<TransferOwnershipButton />}>
              <KeyValue rows={[["Your role", context.role_name], ["Status", profile.data.org_status], ["Currency", `${context.base_currency_symbol} ${context.base_currency_code}`]]} />
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
