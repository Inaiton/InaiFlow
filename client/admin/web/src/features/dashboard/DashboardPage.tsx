"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, Database, FileText, IndianRupee, PlayCircle, Users } from "lucide-react";
import { createColumnHelper } from "@tanstack/react-table";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { KpiCard, PageHeader } from "@/components/ui/misc";
import { StatusBadge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState, QueryState } from "@/components/ui/states";
import { formatBytes, formatINRCompact } from "@/lib/money";
import { fmtDate } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";
import { useDashboard } from "./api";
import { SignupsChart } from "./SignupsChart";

const n = (v: number) => v.toLocaleString("en-IN");
const col = createColumnHelper<Schemas["AdminOrgSummary"]>();
const columns = [
  col.accessor("legal_name", {
    header: "Organization",
    cell: (c) => (
      <div>
        <div className="font-medium text-ink">{c.getValue()}</div>
        <div className="text-xs text-faint">{c.row.original.owner_email}</div>
      </div>
    ),
  }),
  col.accessor("public_join_code", { header: "Code", cell: (c) => <span className="font-mono text-xs">{c.getValue()}</span> }),
  col.accessor("plan_code", { header: "Plan", cell: (c) => c.getValue() ?? "—" }),
  col.accessor("member_count", { header: "Seats" }),
  col.accessor("org_status", { header: "Status", cell: (c) => <StatusBadge status={c.getValue()} /> }),
  col.accessor("created_at", { header: "Created", cell: (c) => fmtDate(c.getValue()) }),
];

export function DashboardPage() {
  const q = useDashboard();
  const router = useRouter();
  return (
    <>
      <PageHeader title="Platform command dashboard" description="All tenants · live" />
      <QueryState query={q}>
        {(d) => (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
              <KpiCard label="Organizations" value={n(d.orgs_total)} sub={`${n(d.orgs_active)} active · ${n(d.orgs_trial)} trial · ${n(d.orgs_suspended)} suspended`} icon={<Building2 />} tone="accent" />
              <KpiCard label="Users" value={n(d.users_total)} icon={<Users />} tone="indigo" />
              <KpiCard label="MRR" value={formatINRCompact(d.mrr_inr)} sub="GST exclusive" icon={<IndianRupee />} tone="teal" />
              <KpiCard label="Vouchers today" value={n(d.vouchers_today)} sub="Across all tenants" icon={<FileText />} tone="sky" />
              <KpiCard label="Active runs" value={n(d.active_runs)} icon={<PlayCircle />} tone="violet" />
              <KpiCard label="Storage" value={formatBytes(d.storage_bytes)} sub="Document vaults" icon={<Database />} tone="orange" />
            </div>
            <div className="grid gap-5 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <CardHeader title="Signups" description="New organizations over time" />
                <CardBody>
                  <SignupsChart points={d.signups_series} />
                </CardBody>
              </Card>
              <Card>
                <CardHeader title="System health" />
                <CardBody className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] text-ink-2">IRP e-Invoice API</span>
                    <StatusBadge status={d.irp_health} />
                  </div>
                  <Link href="/system" className="text-[13px] text-primary hover:underline">
                    Full system status
                  </Link>
                </CardBody>
              </Card>
            </div>
            <Card>
              <CardHeader title="Recent organizations" actions={<Link href="/organizations" className="text-[13px] text-primary hover:underline">All organizations</Link>} />
              {d.recent_orgs.length ? (
                <DataTable data={d.recent_orgs} columns={columns} getRowId={(r) => r.id} onRowClick={(r) => router.push(`/organizations/${r.id}`)} />
              ) : (
                <EmptyState title="No organizations yet" />
              )}
            </Card>
          </div>
        )}
      </QueryState>
    </>
  );
}
