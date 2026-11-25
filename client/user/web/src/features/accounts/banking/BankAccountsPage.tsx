"use client";

import { Landmark } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Badge, Button, Card, DataTable, EmptyState, PageHeader, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { Can } from "@/core/permissions/Can";
import { Bal } from "../components/Amount";
import { QueryState } from "../components/QueryState";
import { BANKING_NAV, SubNav } from "../components/SubNav";
import { useAccHref } from "../lib/api-base";
import { accDate } from "../lib/format";
import { useBankAccounts } from "./api";

type BA = Schemas["BankAccountOut"];

/** /accounts/banking — bank ledgers with book balance and reconciliation status (design: Acc-Banking). */
export function BankAccountsPage() {
  const href = useAccHref();
  const router = useRouter();
  const q = useBankAccounts();
  const cols: ColumnDef<BA, unknown>[] = [
    { accessorKey: "name", header: "Bank account", cell: ({ row: { original: b } }) => <span className="flex flex-col"><span className="font-medium text-fg">{b.name}</span><span className="text-[11.5px] text-fg-muted">{b.bank_account ?? "—"}{b.ifsc ? ` · ${b.ifsc}` : ""}</span></span> },
    { id: "bal", header: "Book balance", meta: { align: "right" }, cell: ({ row: { original: b } }) => <Bal v={b.book_balance} type={b.book_balance_type} /> },
    { accessorKey: "unreconciled_count", header: "Unreconciled", meta: { align: "right" }, cell: ({ getValue }) => { const n = getValue() as number; return n ? <Badge tone="warning">{n} entries</Badge> : <Badge tone="success">All clear</Badge>; } },
    { accessorKey: "last_reconciled_on", header: "Last reconciled", cell: ({ getValue }) => accDate(getValue() as string | null) },
    { id: "act", header: "", cell: ({ row: { original: b } }) => <Button size="sm" variant="secondary" onClick={(e) => { e.stopPropagation(); router.push(href(`/banking/${b.ledger_id}`)); }}>Reconcile</Button> },
  ];
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Banking" }]} title="Banking" description="Bank reconciliation, statement import, cheque books and cheque printing"
        actions={<Can permission="accounts.ledgers_groups" level="WRITE"><Button asChild variant="primary"><Link href={href("/masters/ledgers/new")}>New bank ledger</Link></Button></Can>} />
      <SubNav items={BANKING_NAV} />
      <Card padded={false}>
        <QueryState q={q}>{(list) => <DataTable columns={cols} data={list} getRowId={(b) => b.ledger_id} onRowClick={(b) => router.push(href(`/banking/${b.ledger_id}`))} aria-label="Bank accounts"
          empty={<EmptyState icon={Landmark} title="No bank accounts" description="Create a ledger under Bank Accounts." />} />}</QueryState>
      </Card>
    </>
  );
}
