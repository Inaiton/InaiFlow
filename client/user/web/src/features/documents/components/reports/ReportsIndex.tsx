"use client";

import { FilePlus2, FileText } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, DataTable, EmptyState, ErrorState, PageHeader, Segmented, StatusBadge, type ColumnDef } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { formatDate } from "@/core/dates";
import { Can } from "@/core/permissions/Can";
import { useDocuments, type DocumentSummary } from "../../api/documents";
import { useDocsPath } from "../../paths";

const cols: ColumnDef<DocumentSummary, unknown>[] = [
  { header: "Report", accessorKey: "title", cell: ({ row }) => <span className="font-semibold text-fg">{row.original.title}</span> },
  { header: "Number", cell: ({ row }) => row.original.iso_doc_number ?? "—" },
  { header: "Rev", cell: ({ row }) => row.original.revision_no },
  { header: "Prepared by", accessorKey: "prepared_by_name" },
  { header: "Updated", cell: ({ row }) => formatDate(row.original.updated_at) },
  { header: "Status", cell: ({ row }) => <StatusBadge status={row.original.approval_status} /> },
];
const LIMIT = 25;

/** /documents/editor — reports list; the one primary action is “New inspection report”. */
export function ReportsIndex() {
  const d = useDocsPath();
  const router = useRouter();
  const [source, setSource] = useState<"INTERNAL_TEMPLATE" | "BLANK_ADHOC">("INTERNAL_TEMPLATE");
  const [offset, setOffset] = useState(0);
  const list = useDocuments({ source_type: source, limit: LIMIT, offset });
  const cta = <Can permission="documents.editor" level="WRITE"><Button asChild variant="primary"><Link href={d("/reports/new")}><FilePlus2 /> New inspection report</Link></Button></Can>;
  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Documents", href: d() }, { label: "Inspection reports" }]} title="Inspection reports" description="Pick a template and a run — readings and specs fill in for you"
        actions={<><Can permission="documents.editor" level="WRITE"><Button asChild><Link href={d("/reports/new?blank=1")}>Blank document</Link></Button></Can>{cta}</>} />
      <Card>
        <Segmented aria-label="Kind" value={source} onChange={(v) => { setSource(v); setOffset(0); }} options={[{ value: "INTERNAL_TEMPLATE", label: "From templates" }, { value: "BLANK_ADHOC", label: "Blank & ad-hoc" }]} />
        {list.isError ? <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} /> : (
          <DataTable aria-label="Reports" columns={cols} data={list.data?.items} loading={list.isPending} getRowId={(r) => r.id}
            onRowClick={(r) => router.push(d(r.approval_status === "DRAFT" ? `/editor/${r.id}` : `/editor/${r.id}/review`))}
            pagination={list.data ? { total: list.data.total, limit: LIMIT, offset, onOffsetChange: setOffset } : undefined}
            empty={<EmptyState icon={FileText} tone="sky" title="No reports yet" description="Your first inspection report takes about two minutes." action={cta} />} />
        )}
      </Card>
    </div>
  );
}
