"use client";

import { useDeferredValue, useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { DefinitionList, PageHeader } from "@/components/ui/misc";
import { DataTable } from "@/components/ui/data-table";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, QueryState } from "@/components/ui/states";
import { Dialog, SheetContent } from "@/components/ui/dialog";
import { JsonBlock, JsonDiffView } from "@/components/ui/json-diff-view";
import { useAdminCan } from "@/core/permissions/Can";
import { fmtDateTime } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";
import { useAdmins } from "@/features/admins/api";
import { useAuditLogs, type AuditFilters } from "./api";

type Row = Schemas["PlatformAuditOut"];
const col = createColumnHelper<Row>();
const columns = [
  col.accessor("created_at", { header: "When", cell: (c) => <span className="whitespace-nowrap">{fmtDateTime(c.getValue())}</span> }),
  col.accessor("admin_email", { header: "Admin", cell: (c) => c.getValue() ?? "system" }),
  col.accessor("action", { header: "Action", cell: (c) => <Badge tone="indigo">{c.getValue()}</Badge> }),
  col.accessor("target_type", { header: "Target", cell: (c) => <span className="text-[13px]">{c.getValue()}</span> }),
  col.accessor("target_id", { header: "Target id", cell: (c) => <span className="font-mono text-[11px] text-faint">{c.getValue() ?? "—"}</span> }),
  col.accessor("ip_address", { header: "IP", cell: (c) => <span className="font-mono text-[11px]">{c.getValue() ?? "—"}</span> }),
];

const TARGETS = ["organization", "user", "config", "plan", "invoice", "admin", "impersonation"];

export function AuditLogsPage() {
  const can = useAdminCan();
  const admins = useAdmins(can("GET /admin/admins"));
  const [f, setF] = useState<AuditFilters>({ limit: 50, offset: 0 });
  const action = useDeferredValue(f.action);
  const q = useAuditLogs({ ...f, action });
  const [open, setOpen] = useState<Row | null>(null);
  const set = (p: Partial<AuditFilters>) => setF((x) => ({ ...x, ...p, offset: p.offset ?? 0 }));

  return (
    <>
      <PageHeader title="Platform audit" description="Immutable trail of every platform admin action" />
      <Card>
        <div className="grid grid-cols-2 gap-2 border-b border-line p-3 md:grid-cols-5">
          <Field label="Action">
            <Input value={f.action ?? ""} onChange={(e) => set({ action: e.target.value })} placeholder="e.g. ORG_SUSPEND" />
          </Field>
          <Field label="Target type">
            <NativeSelect value={f.target_type ?? ""} onChange={(e) => set({ target_type: e.target.value })}>
              <option value="">Any</option>
              {TARGETS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="Admin">
            <NativeSelect value={f.admin_id ?? ""} onChange={(e) => set({ admin_id: e.target.value })} disabled={!admins.data}>
              <option value="">Any</option>
              {admins.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.email}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="From">
            <Input type="date" value={f.date_from ?? ""} onChange={(e) => set({ date_from: e.target.value })} />
          </Field>
          <Field label="To">
            <Input type="date" value={f.date_to ?? ""} onChange={(e) => set({ date_to: e.target.value })} />
          </Field>
        </div>
        <QueryState query={q} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="No audit entries match" />}>
          {(d) => (
            <>
              <DataTable data={d.items} columns={columns} getRowId={(r) => r.id} onRowClick={setOpen} />
              <Pagination total={d.total} limit={d.limit} offset={d.offset} onChange={(offset) => set({ offset })} />
            </>
          )}
        </QueryState>
      </Card>
      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        {open ? (
          <SheetContent title={open.action} description={fmtDateTime(open.created_at)}>
            <div className="space-y-5">
              <DefinitionList
                items={[
                  ["Admin", open.admin_email ?? "system"],
                  ["IP address", open.ip_address ?? "—"],
                  ["Target type", open.target_type],
                  ["Target id", <span key="t" className="font-mono text-xs">{open.target_id ?? "—"}</span>],
                ]}
              />
              <div>
                <h4 className="mb-2 text-[13px] font-semibold text-ink">Changes</h4>
                <JsonDiffView before={open.before_state} after={open.after_state} />
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                <div>
                  <h4 className="mb-1 text-xs font-semibold text-faint">Before</h4>
                  <JsonBlock value={open.before_state} />
                </div>
                <div>
                  <h4 className="mb-1 text-xs font-semibold text-faint">After</h4>
                  <JsonBlock value={open.after_state} />
                </div>
              </div>
            </div>
          </SheetContent>
        ) : null}
      </Dialog>
    </>
  );
}
