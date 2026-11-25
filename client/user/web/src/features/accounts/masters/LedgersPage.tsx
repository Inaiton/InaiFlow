"use client";

import { BookOpen } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, DataTable, EmptyState, ErrorState, Field, Input, NativeSelect, PageHeader, SwitchRow, type ColumnDef } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { Can } from "@/core/permissions/Can";
import { Bal } from "../components/Amount";
import { GroupSelect } from "../components/Selects";
import { MASTERS_NAV, SubNav } from "../components/SubNav";
import { useAccHref } from "../lib/api-base";
import { useDebouncedValue } from "../lib/hooks";
import { useRBar } from "../shell/rbar-context";
import { useLedgers, type Ledger } from "./api";

const PAGE = 50;

/** /accounts/masters/ledgers — searchable chart of accounts (design: Acc-Ledgers). */
export function LedgersPage() {
  const href = useAccHref();
  const router = useRouter();
  const [text, setText] = useState("");
  const params = useSearchParams();
  const [group, setGroup] = useState(params.get("group") ?? "");
  const [kind, setKind] = useState("");
  const [inactive, setInactive] = useState(false);
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(text, 250);
  const list = useLedgers({ limit: PAGE, offset, ...(q ? { q } : {}), ...(group ? { group_id: group } : {}), ...(kind === "party" ? { party_only: true } : kind === "bank" ? { bank_only: true } : {}), ...(inactive ? { include_inactive: true } : {}) });
  useRBar([{ id: "create", combo: "alt+c", label: "Create ledger", href: href(`/masters/ledgers/new${group ? `?group=${group}` : ""}`) }, { id: "groups", combo: "alt+h", label: "Groups", href: href("/masters/groups") }], "accounts");
  const columns: ColumnDef<Ledger, unknown>[] = [
    { accessorKey: "name", header: "Ledger", cell: ({ row: { original: l } }) => <span className="flex flex-col"><span className="font-medium text-fg">{l.name}</span>{l.alias ? <span className="text-[11.5px] text-fg-muted">{l.alias}</span> : null}</span> },
    { accessorKey: "group_name", header: "Under group" },
    { id: "gstin", header: "GSTIN", cell: ({ row: { original: l } }) => <span className="font-mono text-[12px]">{l.party_details?.gstin ?? "—"}</span> },
    { id: "state", header: "State", cell: ({ row: { original: l } }) => l.party_details?.state_code ?? "—" },
    { id: "closing", header: "Closing balance", meta: { align: "right" }, cell: ({ row: { original: l } }) => <Bal v={l.closing_balance} type={l.closing_balance_type} /> },
    { id: "status", header: "Status", cell: ({ row: { original: l } }) => (
      <span className="flex gap-1">{l.is_active ? <Badge tone="success">Active</Badge> : <Badge>Inactive</Badge>}{l.system_code ? <Badge tone="indigo">System</Badge> : null}{l.party_details?.msme_type ? <Badge tone="warning">MSME</Badge> : null}</span>
    ) },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Masters", href: href("/masters") }, { label: "Ledgers" }]} title="Ledgers" description="Parties, banks, taxes, income and expense heads"
        actions={<Can permission="accounts.ledgers_groups" level="WRITE"><Button asChild variant="primary"><Link href={href("/masters/ledgers/new")}>New ledger (Alt C)</Link></Button></Can>} />
      <SubNav items={MASTERS_NAV} />
      <Card padded={false}>
        <div className="grid grid-cols-1 gap-3 border-b border-line p-4 md:grid-cols-[minmax(0,1fr)_240px_180px_200px] md:items-end">
          <Field label="Search"><Input autoFocus value={text} onChange={(e) => { setOffset(0); setText(e.target.value); }} placeholder="Name, alias, GSTIN…" /></Field>
          <Field label="Group"><GroupSelect value={group} onValueChange={(v) => { setOffset(0); setGroup(v); }} placeholder="All groups" /></Field>
          <Field label="Show"><NativeSelect value={kind} onChange={(e) => { setOffset(0); setKind(e.target.value); }}><option value="">All ledgers</option><option value="party">Parties</option><option value="bank">Banks</option></NativeSelect></Field>
          <SwitchRow label="Include inactive" checked={inactive} onCheckedChange={(v) => { setOffset(0); setInactive(v); }} />
        </div>
        {list.isError ? <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} /> : (
          <DataTable columns={columns} data={list.data?.items} loading={list.isPending} getRowId={(l) => l.id} onRowClick={(l) => router.push(href(`/masters/ledgers/${l.id}`))} aria-label="Ledgers"
            pagination={list.data ? { total: list.data.total, limit: list.data.limit, offset: list.data.offset, onOffsetChange: setOffset } : undefined}
            empty={<EmptyState icon={BookOpen} title="No ledgers match" description="Create one with Alt C." />} />
        )}
      </Card>
    </>
  );
}
