"use client";

import { Upload } from "lucide-react";
import Link from "next/link";
import { useRef } from "react";
import { toast } from "sonner";
import { Button, Card, DataTable, EmptyState, Tabs, TabsContent, TabsList, TabsTrigger, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { useCan } from "@/core/permissions/Can";
import { Amt } from "../components/Amount";
import { QueryState } from "../components/QueryState";
import { useAccHref } from "../lib/api-base";
import { accDate } from "../lib/format";
import { useGstr2bRecon, useImportGstr2b } from "./api";
import { TaxShell, useMonth } from "./TaxPages";

type Row = Schemas["ReconRow"];
const BUCKETS = [["exact", "Exact match"], ["partial", "Partial / tax mismatch"], ["missing_in_books", "Missing in books"], ["missing_in_portal", "Missing in portal"]] as const;

/** /accounts/taxation/gstr2b — import the portal JSON and reconcile ITC (design: Acc-Tax-2BUpload). */
export function Gstr2bPage() {
  const href = useAccHref();
  const [period, setPeriod] = useMonth();
  const q = useGstr2bRecon(period);
  const imp = useImportGstr2b(period);
  const fileRef = useRef<HTMLInputElement>(null);
  const canWrite = useCan("accounts.taxation", "WRITE");
  const cols: ColumnDef<Row, unknown>[] = [
    { accessorKey: "gstin", header: "Supplier GSTIN", cell: ({ row: { original: r } }) => <span className="flex flex-col"><span className="font-mono text-[12px]">{r.gstin}</span><span className="text-[11.5px] text-fg-muted">{r.supplier_name ?? ""}</span></span> },
    { accessorKey: "invoice_no", header: "Invoice", cell: ({ row: { original: r } }) => (r.voucher_id ? <Link href={href(`/vouchers/${r.voucher_id}`)}>{r.invoice_no}</Link> : r.invoice_no) },
    { accessorKey: "invoice_date", header: "Date", cell: ({ getValue }) => accDate(getValue() as string) },
    { accessorKey: "taxable", header: "Books taxable", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "tax", header: "Books tax", meta: { align: "right" }, cell: ({ getValue }) => <Amt v={getValue() as string} /> },
    { accessorKey: "portal_taxable", header: "Portal taxable", meta: { align: "right" }, cell: ({ getValue }) => (getValue() ? <Amt v={getValue() as string} /> : "—") },
    { accessorKey: "portal_tax", header: "Portal tax", meta: { align: "right" }, cell: ({ getValue }) => (getValue() ? <Amt v={getValue() as string} /> : "—") },
    { accessorKey: "difference", header: "Difference", meta: { align: "right" }, cell: ({ getValue }) => (getValue() ? <Amt v={getValue() as string} /> : "—") },
  ];
  const onFile = async (f: File | undefined) => {
    if (!f) return;
    const r = await imp.mutateAsync(f);
    toast.message(`${r.invoices} invoices imported for ${r.period}`);
  };
  return (
    <TaxShell title="GSTR-2B reconciliation" description="Match supplier uploads against purchase vouchers" period={period} setPeriod={setPeriod}
      actions={canWrite ? <><input ref={fileRef} type="file" accept="application/json,.json" className="sr-only" aria-label="GSTR-2B JSON" onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = ""; }} />
        <Button variant="primary" loading={imp.isPending} onClick={() => fileRef.current?.click()}><Upload />Import GSTR-2B JSON</Button></> : null}>
      <QueryState q={q}>
        {(r) => (
          <Card padded={false}>
            <Tabs defaultValue="partial" className="px-2 pb-2 pt-3">
              <TabsList>{BUCKETS.map(([k, l]) => <TabsTrigger key={k} value={k}>{l} <span className="text-fg-muted">({r[k].length})</span></TabsTrigger>)}</TabsList>
              {BUCKETS.map(([k, l]) => <TabsContent key={k} value={k}><DataTable columns={cols} data={r[k]} getRowId={(x) => `${x.gstin}-${x.invoice_no}`} aria-label={l} empty={<EmptyState title={`Nothing in “${l}”`} />} /></TabsContent>)}
            </Tabs>
          </Card>
        )}
      </QueryState>
    </TaxShell>
  );
}
