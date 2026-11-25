"use client";

import Link from "next/link";
import { useState } from "react";
import { Archive, CalendarPlus, Crown, Eye, Layers, Play, Pause } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { DefinitionList, KpiCard, PageHeader } from "@/components/ui/misc";
import { JsonBlock } from "@/components/ui/json-diff-view";
import { QueryState } from "@/components/ui/states";
import { useAdminCan } from "@/core/permissions/Can";
import { fmtDate, fmtDateTime, fmtRelative } from "@/lib/dates";
import { formatBytes } from "@/lib/money";
import type { Schemas } from "@/lib/api/client";
import { useOrg } from "./api";
import type { LifecycleAction } from "./constants";
import { LifecycleDialog } from "./LifecycleDialog";
import { PlanDialog } from "./PlanDialog";
import { TransferOwnerDialog } from "./TransferOwnerDialog";
import { ImpersonateDialog } from "./ImpersonateDialog";

type Modal = null | "plan" | "transfer" | "impersonate";

function Actions({ org, onLifecycle, onModal }: { org: Schemas["AdminOrgDetail"]; onLifecycle: (a: LifecycleAction) => void; onModal: (m: Modal) => void }) {
  const can = useAdminCan();
  const s = org.org_status;
  return (
    <div className="flex flex-wrap gap-2">
      {can("org.lifecycle.ACTIVATE") && s !== "ACTIVE" && s !== "ARCHIVED" ? (
        <Button onClick={() => onLifecycle("ACTIVATE")}>
          <Play /> Activate
        </Button>
      ) : null}
      {can("org.lifecycle.EXTEND_TRIAL") && s === "TRIAL" ? (
        <Button onClick={() => onLifecycle("EXTEND_TRIAL")}>
          <CalendarPlus /> Extend trial
        </Button>
      ) : null}
      {can("PATCH /admin/organizations/{org_id}/plan") && s !== "ARCHIVED" ? (
        <Button onClick={() => onModal("plan")}>
          <Layers /> Change plan
        </Button>
      ) : null}
      {can("POST /admin/organizations/{org_id}/impersonate") && s !== "ARCHIVED" ? (
        <Button onClick={() => onModal("impersonate")}>
          <Eye /> View as support
        </Button>
      ) : null}
      {can("POST /admin/organizations/{org_id}/transfer-owner") && s !== "ARCHIVED" ? (
        <Button onClick={() => onModal("transfer")}>
          <Crown /> Transfer owner
        </Button>
      ) : null}
      {can("org.lifecycle.SUSPEND") && (s === "ACTIVE" || s === "TRIAL") ? (
        <Button variant="danger-outline" onClick={() => onLifecycle("SUSPEND")}>
          <Pause /> Suspend
        </Button>
      ) : null}
      {can("org.lifecycle.ARCHIVE") && s !== "ARCHIVED" ? (
        <Button variant="danger-outline" onClick={() => onLifecycle("ARCHIVE")}>
          <Archive /> Archive
        </Button>
      ) : null}
    </div>
  );
}

export function OrgDetailPage({ id }: { id: string }) {
  const q = useOrg(id);
  const [lifecycle, setLifecycle] = useState<LifecycleAction | null>(null);
  const [modal, setModal] = useState<Modal>(null);
  return (
    <QueryState query={q}>
      {(o) => (
        <>
          <PageHeader
            crumbs={
              <>
                <Link href="/organizations" className="hover:underline">
                  Organizations
                </Link>{" "}
                / {o.workspace_slug}
              </>
            }
            title={
              <span className="flex items-center gap-2">
                {o.legal_name} <StatusBadge status={o.org_status} />
              </span>
            }
            description={`${o.public_join_code} · GSTIN ${o.gstin ?? "—"} · owner ${o.owner_email}`}
          />
          <Card className="mb-5">
            <CardBody>
              <Actions org={o} onLifecycle={setLifecycle} onModal={setModal} />
            </CardBody>
          </Card>
          <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
            <KpiCard label="Members" value={o.member_count} sub={`${o.external_count} external`} />
            <KpiCard label="Vouchers" value={o.voucher_count.toLocaleString("en-IN")} />
            <KpiCard label="Period runs" value={o.run_count.toLocaleString("en-IN")} />
            <KpiCard label="Storage" value={formatBytes(o.storage_used_bytes)} />
            <KpiCard label="Plan" value={o.plan_code ?? "—"} sub={o.trial_ends_at ? `Trial ends ${fmtRelative(o.trial_ends_at)}` : undefined} />
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader title="Profile" />
              <CardBody>
                <DefinitionList
                  items={[
                    ["Legal name", o.legal_name],
                    ["Workspace", o.workspace_slug],
                    ["Join code", <span key="c" className="font-mono">{o.public_join_code}</span>],
                    ["Industry", o.industry_type],
                    ["City / state", `${o.city} · ${o.state_code}`],
                    ["GSTIN", o.gstin ?? "—"],
                    ["Contact email", o.contact_email],
                    ["Contact phone", o.contact_phone],
                    ["Created", fmtDateTime(o.created_at)],
                    ["Trial ends", fmtDate(o.trial_ends_at)],
                  ]}
                />
              </CardBody>
            </Card>
            <div className="space-y-5">
              <Card>
                <CardHeader title="Owner" description="Owner recovery: transfer to another active member" />
                <CardBody>
                  <DefinitionList
                    items={[
                      ["Name", <Link key="o" href={`/users/${o.owner_user_id}`} className="text-primary hover:underline">{o.owner_name}</Link>],
                      ["Email", o.owner_email],
                    ]}
                  />
                </CardBody>
              </Card>
              <Card>
                <CardHeader title="Quota overrides" description="Applied on top of the plan's limits" />
                <CardBody>
                  {o.quota_overrides && typeof o.quota_overrides === "object" && Object.keys(o.quota_overrides).length ? <JsonBlock value={o.quota_overrides} /> : <p className="text-[13px] text-faint">None — plan defaults apply.</p>}
                </CardBody>
              </Card>
            </div>
          </div>
          <LifecycleDialog key={lifecycle ?? "none"} orgId={o.id} orgName={o.legal_name} action={lifecycle} onClose={() => setLifecycle(null)} />
          {modal === "plan" ? <PlanDialog org={o} open onClose={() => setModal(null)} /> : null}
          {modal === "transfer" ? <TransferOwnerDialog org={o} open onClose={() => setModal(null)} /> : null}
          {modal === "impersonate" ? <ImpersonateDialog org={o} open onClose={() => setModal(null)} /> : null}
        </>
      )}
    </QueryState>
  );
}
