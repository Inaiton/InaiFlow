"use client";

import { useDeferredValue, useState } from "react";
import { useRouter } from "next/navigation";
import { createColumnHelper } from "@tanstack/react-table";
import { Search } from "lucide-react";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/misc";
import { Input, NativeSelect } from "@/components/ui/input";
import { DataTable } from "@/components/ui/data-table";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, QueryState } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/badge";
import { fmtDate, fmtRelative } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";
import { usePlans } from "@/features/plans/api";
import { useOrgs, type OrgFilters } from "./api";
import { INDUSTRIES, ORG_STATUSES } from "./constants";

const col = createColumnHelper<Schemas["AdminOrgSummary"]>();
const columns = [
  col.accessor("legal_name", {
    header: "Organization",
    cell: (c) => (
      <div>
        <div className="font-medium text-ink">{c.getValue()}</div>
        <div className="text-xs text-faint">
          {c.row.original.workspace_slug} · {c.row.original.owner_email}
        </div>
      </div>
    ),
  }),
  col.accessor("public_join_code", { header: "Code", cell: (c) => <span className="font-mono text-xs">{c.getValue()}</span> }),
  col.accessor("gstin", { header: "GSTIN", cell: (c) => <span className="font-mono text-xs">{c.getValue() ?? "—"}</span> }),
  col.accessor("industry_type", { header: "Industry" }),
  col.accessor("plan_code", { header: "Plan", cell: (c) => c.getValue() ?? "—" }),
  col.accessor("member_count", { header: "Seats" }),
  col.accessor("org_status", {
    header: "Status",
    cell: (c) => (
      <div className="flex flex-col items-start gap-0.5">
        <StatusBadge status={c.getValue()} />
        {c.getValue() === "TRIAL" && c.row.original.trial_ends_at ? <span className="text-[11px] text-faint">ends {fmtRelative(c.row.original.trial_ends_at)}</span> : null}
      </div>
    ),
  }),
  col.accessor("created_at", { header: "Created", cell: (c) => fmtDate(c.getValue()) }),
];

export function OrgDirectoryPage() {
  const router = useRouter();
  const plans = usePlans();
  const [f, setF] = useState<OrgFilters>({ limit: 25, offset: 0 });
  const q = useDeferredValue(f.q);
  const list = useOrgs({ ...f, q });
  const set = (patch: Partial<OrgFilters>) => setF((p) => ({ ...p, ...patch, offset: patch.offset ?? 0 }));

  return (
    <>
      <PageHeader title="Organizations" description="Lifecycle, plans, quotas and audited support access" />
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <div className="relative min-w-64 flex-1">
            <Search className="absolute left-2.5 top-2.5 size-4 text-faint" />
            <Input className="pl-8" placeholder="Search name, slug, GSTIN, code…" value={f.q ?? ""} onChange={(e) => set({ q: e.target.value })} aria-label="Search organizations" />
          </div>
          <NativeSelect className="w-40" value={f.status ?? ""} onChange={(e) => set({ status: e.target.value })} aria-label="Status filter">
            <option value="">All statuses</option>
            {ORG_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.charAt(0) + s.slice(1).toLowerCase()}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect className="w-44" value={f.plan_code ?? ""} onChange={(e) => set({ plan_code: e.target.value })} aria-label="Plan filter">
            <option value="">All plans</option>
            {plans.data?.map((p) => (
              <option key={p.id} value={p.plan_code}>
                {p.name}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect className="w-48" value={f.industry ?? ""} onChange={(e) => set({ industry: e.target.value })} aria-label="Industry filter">
            <option value="">All industries</option>
            {INDUSTRIES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ").toLowerCase()}
              </option>
            ))}
          </NativeSelect>
        </div>
        <QueryState query={list} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="No organizations match" description="Try clearing filters." />}>
          {(d) => (
            <>
              <DataTable data={d.items} columns={columns} getRowId={(r) => r.id} onRowClick={(r) => router.push(`/organizations/${r.id}`)} />
              <Pagination total={d.total} limit={d.limit} offset={d.offset} onChange={(offset) => set({ offset })} />
            </>
          )}
        </QueryState>
      </Card>
    </>
  );
}
