"use client";

import { UserPlus } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useOrg } from "@/core/org/OrgProvider";
import { Can } from "@/core/permissions/Can";
import { Badge, Button, Card, PageHeader, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { useMembers, useOrgInvitations, useOrgJoinRequests } from "../api";
import { InvitationsTab, JoinRequestsTab } from "./InvitesAndRequests";
import { InviteDialog } from "./MemberDialogs";
import { MembersTab } from "./MembersTab";

/** /o/[slug]/organization/members (design: Org-Members*.dc.html). */
export function MembersPage() {
  const { slug } = useOrg();
  const params = useSearchParams();
  const router = useRouter();
  const [inviteOpen, setInviteOpen] = useState(params.get("invite") === "1");
  const members = useMembers();
  const invites = useOrgInvitations("PENDING");
  const requests = useOrgJoinRequests("PENDING");
  const all = members.data ?? [];
  const external = all.filter((m) => m.is_external).length;
  const closeInvite = (o: boolean) => {
    setInviteOpen(o);
    if (!o && params.get("invite")) router.replace(`/o/${slug}/organization/members`);
  };
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Organization", href: `/o/${slug}/organization/profile` }, { label: "Members" }]}
        title="Members & access"
        description={members.data ? `${all.length - external} internal · ${external} external collaborators` : "People who can work in this organization"}
        actions={<Can permission="organization.members" level="FULL"><Button variant="primary" onClick={() => setInviteOpen(true)}><UserPlus /> Invite member</Button></Can>}
      />
      <Card padded>
        <Tabs defaultValue="members">
          <TabsList>
            <TabsTrigger value="members">Active members <Badge>{all.length}</Badge></TabsTrigger>
            <TabsTrigger value="invitations">Invitations <Badge>{invites.data?.length ?? 0}</Badge></TabsTrigger>
            <TabsTrigger value="requests">Join requests {requests.data?.length ? <Badge tone="warning">{requests.data.length}</Badge> : <Badge>0</Badge>}</TabsTrigger>
          </TabsList>
          <TabsContent value="members"><MembersTab /></TabsContent>
          <TabsContent value="invitations"><InvitationsTab /></TabsContent>
          <TabsContent value="requests"><JoinRequestsTab /></TabsContent>
        </Tabs>
      </Card>
      <InviteDialog open={inviteOpen} onOpenChange={closeInvite} />
    </>
  );
}
