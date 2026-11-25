"use client";

import { History } from "lucide-react";
import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import type { Schemas } from "@/core/api/types";
import { formatDateTime } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import {
  Badge, Button, Card, DataTable, DatePicker, EmptyState, ErrorState, Field, JsonBlock, JsonDiff, KeyValue, NativeSelect, PageHeader, Sheet, SheetContent, titleCase, type ColumnDef,
} from "@/components/ui";
import { useAuditLogs, type AuditQuery } from "../api-rbac";

type Log = Schemas["AuditLogOut"];
const MODULES = ["ACCOUNTS", "OPERATIONS", "DOCUMENTS", "ORGANIZATION", "PAYROLL", "TAXATION", "IDENTITY"];
const ACTIONS = ["CREATE", "UPDATE", "DELETE", "APPROVE", "LOCK", "OVERRIDE", "EXPORT", "LOGIN", "CANCEL"];
const ACTION_TONE: Record<string, "success" | "indigo" | "danger" | "warning" | "violet" | "gray"> = { CREATE: "success", UPDATE: "indigo", DELETE: "danger", OVERRIDE: "warning", APPROVE: "violet", LOCK: "violet" };
const PAGE = 50;

function AuditDetail({ log, onClose }: { log: Log; onClose: () => void }) {
  return (
    <Sheet open onOpenChange={(o) => !o && onClose()}>
      <SheetContent title={`${log.action} · ${titleCase(log.entity_type)}`} description={formatDateTime(log.created_at)} width={640}>
        <div className="flex flex-col gap-4">
          <KeyValue rows={[
            ["User", log.user_name ?? (log.actor_type === "SYSTEM" ? "System" : log.actor_type)], ["Role", log.role_code], ["Module", log.module],
            ["Entity", <span key="e" className="font-mono text-xs">{log.entity_type} · {log.entity_id}</span>], ["IP address", log.ip_address ?? "—"], ["Reason", log.reason ?? "—"],
          ]} />
          <section className="flex flex-col gap-2"><h3 className="text-[13px] font-semibold text-fg">Changes</h3><JsonDiff before={log.before_diff} after={log.after_diff} /></section>
          <details className="rounded-xl border border-line px-3 py-2">
            <summary className="cursor-pointer text-[13px] font-medium text-fg">Raw before / after</summary>
            <div className="mt-2 grid gap-2 md:grid-cols-2"><JsonBlock value={log.before_diff} /><JsonBlock value={log.after_diff} /></div>
          </details>
          <p className="text-xs text-fg-muted">Append-only. This entry can’t be edited or deleted, including by the Org owner.</p>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** /o/[slug]/organization/audit-logs (design: Org-Audit*.dc.html). */
export function AuditLogPage() {
  const { slug } = useOrg();
  const [filters, setFilters] = useState<Omit<AuditQuery, "limit" | "offset">>({});
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<Log | null>(null);
  const logs = useAuditLogs({ ...filters, limit: PAGE, offset });
  const setF = (k: keyof typeof filters, v: string | null) => {
    setOffset(0);
    setFilters((f) => ({ ...f, [k]: v || undefined }));
  };
  const columns: ColumnDef<Log, unknown>[] = [
    { accessorKey: "created_at", header: "Time", cell: ({ getValue }) => <span className="tabular whitespace-nowrap">{formatDateTime(getValue() as string)}</span> },
    { id: "user", header: "User", cell: ({ row: { original: l } }) => <span className="flex flex-col"><span className="font-medium text-fg">{l.user_name ?? titleCase(l.actor_type)}</span><span className="text-xs text-fg-muted">{l.role_code}</span></span> },
    { accessorKey: "action", header: "Action", cell: ({ getValue }) => <Badge tone={ACTION_TONE[getValue() as string] ?? "gray"}>{getValue() as string}</Badge> },
    { accessorKey: "module", header: "Module", cell: ({ getValue }) => titleCase(getValue() as string) },
    { accessorKey: "entity_type", header: "Record", cell: ({ row: { original: l } }) => <span>{titleCase(l.entity_type)}{l.reason ? <span className="block text-xs text-fg-muted">{l.reason}</span> : null}</span> },
    { accessorKey: "ip_address", header: "IP", cell: ({ getValue }) => <span className="tabular text-xs">{(getValue() as string | null) ?? "—"}</span> },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Organization", href: `/o/${slug}/organization/profile` }, { label: "Audit log" }]} title="Audit trail" description="Every create, edit, approval, lock, export and sign-in across all modules" />
      <Card>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Field label="Module"><NativeSelect value={filters.module ?? ""} onChange={(e) => setF("module", e.target.value)}><option value="">All modules</option>{MODULES.map((m) => <option key={m} value={m}>{titleCase(m)}</option>)}</NativeSelect></Field>
          <Field label="Action"><NativeSelect value={filters.action ?? ""} onChange={(e) => setF("action", e.target.value)}><option value="">All actions</option>{ACTIONS.map((a) => <option key={a} value={a}>{titleCase(a)}</option>)}</NativeSelect></Field>
          <Field label="From"><DatePicker value={filters.date_from} onValueChange={(v) => setF("date_from", v)} /></Field>
          <Field label="To"><DatePicker value={filters.date_to} onValueChange={(v) => setF("date_to", v)} /></Field>
          <div className="flex items-end"><Button variant="ghost" onClick={() => { setFilters({}); setOffset(0); }}>Clear filters</Button></div>
        </div>
        {logs.isError ? <ErrorState message={describeError(logs.error)} onRetry={() => void logs.refetch()} /> : (
          <DataTable columns={columns} data={logs.data?.items} loading={logs.isPending} onRowClick={setOpen} aria-label="Audit log"
            pagination={logs.data ? { total: logs.data.total, limit: logs.data.limit, offset: logs.data.offset, onOffsetChange: setOffset } : undefined}
            empty={<EmptyState icon={History} title="No events match" description="Try a wider date range or clear the filters." />} />
        )}
      </Card>
      {open ? <AuditDetail log={open} onClose={() => setOpen(null)} /> : null}
    </>
  );
}
