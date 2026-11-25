"use client";

import { Download, History, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, DataTable, DatePicker, EmptyState, Field, FieldRow, JsonDiff, PageHeader, Sheet, SheetContent, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { formatDateTime } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { Can, useCan } from "@/core/permissions/Can";
import { QueryState } from "../components/QueryState";
import { useAccHref } from "../lib/api-base";
import { humanize } from "../lib/format";
import { usePeriod } from "../lib/use-period";
import { useAccountsAuditLog, useExceptions, useTallyExport } from "../reports/api";

type Ex = Schemas["ExceptionOut"];
type Log = Schemas["AuditLogOut"];

function Exceptions() {
  const { slug } = useOrg();
  const q = useExceptions();
  const cols: ColumnDef<Ex, unknown>[] = [
    { accessorKey: "severity", header: "Severity", cell: ({ getValue }) => <Badge tone={getValue() === "ERROR" || getValue() === "HIGH" ? "danger" : "warning"}>{getValue() as string}</Badge> },
    { accessorKey: "kind", header: "Kind", cell: ({ getValue }) => humanize(getValue() as string) },
    { accessorKey: "message", header: "Message", cell: ({ row: { original: e } }) => (e.link ? <Link href={e.link.startsWith("/") ? `/o/${slug}${e.link}` : e.link}>{e.message}</Link> : e.message) },
  ];
  return <Card padded={false} title="Exceptions" description="Negative stock, negative cash, unbalanced or unreconciled items, overdue MSME bills"><QueryState q={q}>{(rows) => <DataTable columns={cols} data={rows} getRowId={(e) => `${e.kind}-${e.entity_id ?? e.message}`} aria-label="Exceptions" empty={<EmptyState icon={ShieldCheck} tone="success" title="No exceptions" />} />}</QueryState></Card>;
}

function TallyExport() {
  const { period } = usePeriod();
  const [from, setFrom] = useState(period.from);
  const [to, setTo] = useState(period.to);
  const exp = useTallyExport();
  return (
    <Card title="Tally XML export" description="Masters and vouchers for TallyPrime import (import from Tally is not available yet)">
      <FieldRow>
        <Field label="From"><DatePicker value={from} onValueChange={(v) => v && setFrom(v)} /></Field>
        <Field label="To"><DatePicker value={to} onValueChange={(v) => v && setTo(v)} /></Field>
      </FieldRow>
      <Button variant="secondary" className="self-start" disabled={from > to} loading={exp.isPending} onClick={() => exp.mutate({ date_from: from, date_to: to })}><Download />Download XML</Button>
    </Card>
  );
}

function EditLog() {
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<Log | null>(null);
  const q = useAccountsAuditLog({ limit: 50, offset }, true);
  const cols: ColumnDef<Log, unknown>[] = [
    { accessorKey: "created_at", header: "Time", cell: ({ getValue }) => <span className="tabular whitespace-nowrap">{formatDateTime(getValue() as string)}</span> },
    { accessorKey: "user_name", header: "User", cell: ({ row: { original: l } }) => l.user_name ?? humanize(l.actor_type) },
    { accessorKey: "action", header: "Action", cell: ({ getValue }) => <Badge tone="indigo">{getValue() as string}</Badge> },
    { accessorKey: "entity_type", header: "Record", cell: ({ row: { original: l } }) => <span>{humanize(l.entity_type)}{l.reason ? <span className="block text-[11.5px] text-fg-muted">{l.reason}</span> : null}</span> },
  ];
  return (
    <Card padded={false} title="Edit log (MCA / CARO audit trail)" description="Immutable · every create, alteration and cancellation in Accounts">
      <QueryState q={q}>{(page) => <DataTable columns={cols} data={page.items} getRowId={(l) => l.id} onRowClick={setOpen} aria-label="Accounts edit log" pagination={{ total: page.total, limit: page.limit, offset: page.offset, onOffsetChange: setOffset }} empty={<EmptyState icon={History} title="No events yet" />} />}</QueryState>
      <Sheet open={Boolean(open)} onOpenChange={(o) => !o && setOpen(null)}>
        {open ? <SheetContent title={`${open.action} · ${humanize(open.entity_type)}`} description={formatDateTime(open.created_at)} width={640}><JsonDiff before={open.before_diff} after={open.after_diff} /></SheetContent> : null}
      </Sheet>
    </Card>
  );
}

/** /accounts/utilities — exceptions, Tally XML export, accounts edit log (design: Acc-Utilities). */
export function UtilitiesPage() {
  const href = useAccHref();
  const canAudit = useCan("organization.audit_logs", "READ");
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Utilities" }]} title="Utilities" description="Exceptions, data export and the audit trail"
        actions={<Button asChild variant="secondary"><Link href={href("/settings")}>Accounts settings (F12)</Link></Button>} />
      <Exceptions />
      <Can permission="accounts.reports" level="FULL"><TallyExport /></Can>
      {canAudit ? <EditLog /> : <p className="text-[12.5px] text-fg-muted">The accounts edit log needs Read access to organization.audit_logs. Each voucher’s own edit log is on the voucher.</p>}
    </>
  );
}
