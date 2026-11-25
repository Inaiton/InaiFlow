import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/page-header";
import { Invitations } from "@/features/me/components/Invitations";
import { JoinRequests } from "@/features/me/components/JoinRequests";
import { OrgCards } from "@/features/me/components/OrgCards";

export const metadata: Metadata = { title: "My organizations" };
export default function Page() {
  return (
    <>
      <PageHeader crumbs={[{ label: "Personal space", href: "/me" }, { label: "My organizations" }]} title="My organizations" description="Open a workspace, accept invitations or request to join one" />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex min-w-0 flex-col gap-4">
          <OrgCards />
          <Invitations alwaysShow />
        </div>
        <JoinRequests />
      </div>
    </>
  );
}
