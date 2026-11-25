"use client";

import { UserPlus } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, PageHeader, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { Can } from "@/core/permissions/Can";
import { useOpsPath } from "../../paths";
import { useReadiness } from "../../api/iso";
import { AuditorInviteDialog } from "./AuditorInviteDialog";
import { CalibrationTab } from "./CalibrationTab";
import { ChecklistTab } from "./ChecklistTab";
import { NcrTab } from "./NcrTab";
import { ReadinessOverview } from "./ReadinessOverview";

const TABS = ["overview", "ncr", "calibration", "checklist"] as const;
type Tab = (typeof TABS)[number];

/** /operations/iso-compliance — readiness, NCR/CAPA, calibration register, clause checklist (design Ops-ISO*). */
export function IsoPage() {
  const p = useOpsPath();
  const params = useSearchParams();
  const router = useRouter();
  const initial = params.get("tab");
  const [tab, setTab] = useState<Tab>(TABS.includes(initial as Tab) ? (initial as Tab) : "overview");
  const [invite, setInvite] = useState(false);
  const readiness = useReadiness();
  const change = (t: string) => {
    setTab(t as Tab);
    router.replace(p(`/iso-compliance?tab=${t}`), { scroll: false });
  };
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        crumbs={[{ label: "Operations", href: p() }, { label: "ISO compliance" }]}
        title="ISO 9001 compliance"
        description="Everything an auditor asks for, kept up to date as you work"
        actions={<Can permission="operations.iso_compliance" level="FULL"><Button variant="primary" onClick={() => setInvite(true)}><UserPlus /> Invite auditor</Button></Can>}
      />
      <Card>
        <Tabs value={tab} onValueChange={change}>
          <TabsList>
            <TabsTrigger value="overview">Readiness</TabsTrigger>
            <TabsTrigger value="ncr">NCR & CAPA {readiness.data?.open_ncrs ? <Badge tone="danger">{readiness.data.open_ncrs}</Badge> : null}</TabsTrigger>
            <TabsTrigger value="calibration">Calibration {readiness.data?.expired_instruments ? <Badge tone="danger">{readiness.data.expired_instruments}</Badge> : null}</TabsTrigger>
            <TabsTrigger value="checklist">Clause checklist</TabsTrigger>
          </TabsList>
          <TabsContent value="overview"><ReadinessOverview onGo={change} /></TabsContent>
          <TabsContent value="ncr"><NcrTab /></TabsContent>
          <TabsContent value="calibration"><CalibrationTab /></TabsContent>
          <TabsContent value="checklist"><ChecklistTab /></TabsContent>
        </Tabs>
      </Card>
      <AuditorInviteDialog open={invite} onOpenChange={setInvite} />
    </div>
  );
}
