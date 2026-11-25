"use client";

import { describeError } from "@/core/api/error-messages";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { useMe, useUploadMeFile } from "../api";
import { ImageUploadCard } from "./ImageUploadCard";
import { MfaCard } from "./MfaCard";
import { PasswordForm } from "./PasswordForm";
import { ProfileForm } from "./ProfileForm";
import { SessionsCard } from "./SessionsCard";

/** /me/security (design: Me-Security.dc.html). */
export function SecurityPage() {
  const me = useMe();
  const avatar = useUploadMeFile("AVATAR");
  const signature = useUploadMeFile("SIGNATURE");
  return (
    <>
      <PageHeader crumbs={[{ label: "Personal space", href: "/me" }, { label: "Profile & security" }]} title="Profile & security" description="Your identity, password, two-factor and devices" />
      {me.isPending ? <Skeleton className="h-64" /> : me.isError ? <ErrorState message={describeError(me.error)} onRetry={() => void me.refetch()} /> : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div className="flex min-w-0 flex-col gap-4">
            <ProfileForm me={me.data} />
            <MfaCard enabled={me.data.mfa_enabled} />
            <SessionsCard />
          </div>
          <div className="flex min-w-0 flex-col gap-4">
            <ImageUploadCard title="Photo" description="Shown to teammates in every organization" imageUrl={me.data.avatar_url}
              placeholder={<span className="text-[12.5px] text-fg-muted">No photo</span>} hint="PNG, JPEG or WebP · up to 2 MB" uploading={avatar.isPending} onFile={(f) => avatar.mutate(f)} />
            <div id="signature">
              <ImageUploadCard title="Digital signature" description="Stamped when you approve vouchers, SOPs and QC gates" imageUrl={me.data.signature_url}
                placeholder={<span className="text-[12.5px] text-fg-muted">No signature uploaded</span>} hint="PNG with transparent background, ≥ 600 × 200 px" uploading={signature.isPending} onFile={(f) => signature.mutate(f)} />
            </div>
            <PasswordForm />
          </div>
        </div>
      )}
    </>
  );
}
