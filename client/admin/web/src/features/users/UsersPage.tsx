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
import { Badge } from "@/components/ui/badge";
import { Forbidden } from "@/components/shell/AppShell";
import { useAdminCan } from "@/core/permissions/Can";
import { fmtDate, fmtRelative } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";
import { useUsers, type UserFilters } from "./api";

const col = createColumnHelper<Schemas["AdminUserSummary"]>();
const columns = [
  col.accessor("full_name", {
    header: "User",
    cell: (c) => (
      <div>
        <div className="font-medium text-ink">{c.getValue()}</div>
        <div className="text-xs text-faint">{c.row.original.email}</div>
      </div>
    ),
  }),
  col.accessor("org_count", { header: "Orgs" }),
  col.display({
    id: "flags",
    header: "Security",
    cell: ({ row: { original: u } }) => (
      <div className="flex flex-wrap gap-1">
        {u.is_email_verified ? <Badge tone="success">Verified</Badge> : <Badge tone="warning">Unverified</Badge>}
        {u.mfa_enabled ? <Badge tone="indigo">MFA</Badge> : null}
        {u.is_suspended ? <Badge tone="danger">Suspended</Badge> : null}
      </div>
    ),
  }),
  col.accessor("last_login_at", { header: "Last login", cell: (c) => fmtRelative(c.getValue()) }),
  col.accessor("created_at", { header: "Joined", cell: (c) => fmtDate(c.getValue()) }),
];

export function UsersPage() {
  const can = useAdminCan();
  const router = useRouter();
  const [f, setF] = useState<UserFilters>({ limit: 25, offset: 0 });
  const q = useDeferredValue(f.q);
  const allowed = can("GET /admin/users");
  const list = useUsers({ ...f, q }, allowed);
  if (!allowed) return <Forbidden />;
  const set = (patch: Partial<UserFilters>) => setF((p) => ({ ...p, ...patch, offset: patch.offset ?? 0 }));
  return (
    <>
      <PageHeader title="Global users" description="Every person with an InaiFlow login, across all organizations" />
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <div className="relative min-w-64 flex-1">
            <Search className="absolute left-2.5 top-2.5 size-4 text-faint" />
            <Input className="pl-8" placeholder="Search name or email…" value={f.q ?? ""} onChange={(e) => set({ q: e.target.value })} aria-label="Search users" />
          </div>
          <NativeSelect
            className="w-44"
            value={f.suspended === undefined ? "" : String(f.suspended)}
            onChange={(e) => set({ suspended: e.target.value === "" ? undefined : e.target.value === "true" })}
            aria-label="Suspension filter"
          >
            <option value="">All users</option>
            <option value="false">Not suspended</option>
            <option value="true">Suspended</option>
          </NativeSelect>
        </div>
        <QueryState query={list} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="No users match" />}>
          {(d) => (
            <>
              <DataTable data={d.items} columns={columns} getRowId={(r) => r.id} onRowClick={(r) => router.push(`/users/${r.id}`)} />
              <Pagination total={d.total} limit={d.limit} offset={d.offset} onChange={(offset) => set({ offset })} />
            </>
          )}
        </QueryState>
      </Card>
    </>
  );
}
