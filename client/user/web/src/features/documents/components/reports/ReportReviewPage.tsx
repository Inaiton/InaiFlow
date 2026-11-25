"use client";

import { AlertTriangle, ArrowLeft, CheckCircle2, Download } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button, Card, ErrorState, PageHeader, Skeleton, StatusBadge } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { add, cmp, formatQty } from "@/core/money";
import { useDocument, useExportDocument } from "../../api/documents";
import { useRunContext } from "../../api/context";
import { normalizeBlocks, qcRows, signatureRoles } from "../../lib/blocks";
import { saveBlob } from "../../lib/transfer";
import { useDocsPath } from "../../paths";
import { ApprovalPanel } from "../approval/ApprovalPanel";
import { BlockView } from "../blocks/BlockView";
import { ReportSteps } from "./ReportSteps";

function Check({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-[13px]">
      {ok ? <CheckCircle2 className="mt-0.5 size-4 flex-none text-success" aria-hidden /> : <AlertTriangle className="mt-0.5 size-4 flex-none text-warning" aria-hidden />}
      <span className="text-fg-2">{children}</span>
    </li>
  );
}

/** Step 3 — review & sign (design Doc-Report-Review): read-only page, quick checks, ISO approval, export. */
export function ReportReviewPage({ docId }: { docId: string }) {
  const d = useDocsPath();
  const router = useRouter();
  const doc = useDocument(docId);
  const run = useRunContext(doc.data?.linked_period_run_id ?? null);
  const exp = useExportDocument(docId);
  if (doc.isError) return <ErrorState message={describeError(doc.error)} onRetry={() => void doc.refetch()} />;
  if (!doc.data) return <Skeleton className="h-[70vh]" />;
  const x = doc.data;
  const blocks = normalizeBlocks(x.rich_content);
  const rows = blocks.flatMap((b) => (b.type === "qc_table" ? qcRows(b) : []));
  const fails = rows.filter((r) => /fail/i.test(r.result)).length;
  const auto = rows.filter((r) => r.auto).length;
  const step = run.data?.steps.find((s) => s.id === x.linked_step_id);
  const signers = blocks.flatMap((b) => (b.type === "signature" ? signatureRoles(b) : []));
  const names = [x.prepared_by_name, x.reviewed_by_name, x.approved_by_name];
  const stamps = Object.fromEntries(signers.map((r, i) => [r, names[Math.min(i, 2)] ?? null]));
  const exportAs = async (f: "pdf" | "docx") => {
    try { saveBlob(await exp.mutateAsync(f), `${x.title}.${f}`); } catch (e) { toast.error(describeError(e)); }
  };
  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Documents", href: d() }, { label: "Inspection report", href: d("/editor") }, { label: "Review & sign" }]}
        title={<span className="flex items-center gap-2">Review & sign <StatusBadge status={x.approval_status} /></span>} description={x.title}
        actions={<>
          {x.approval_status === "DRAFT" ? <Button asChild><Link href={d(`/editor/${x.id}`)}><ArrowLeft /> Back to results</Link></Button> : null}
          <Button onClick={() => void exportAs("pdf")} loading={exp.isPending}><Download /> Save PDF</Button>
          <Button onClick={() => void exportAs("docx")}>.docx</Button>
        </>} />
      <ReportSteps current={2} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <BlockView blocks={blocks} stamps={stamps} />
        <div className="flex flex-col gap-4">
          <Card title="Quick check">
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {step ? (
                <Check ok={cmp(add(step.accepted_qty, step.rejected_qty, step.rework_qty), step.input_qty) === 0}>
                  Units add up · {formatQty(step.accepted_qty)} accepted + {formatQty(step.rejected_qty)} rejected{step.rework_qty !== "0" ? ` + ${formatQty(step.rework_qty)} rework` : ""} = {formatQty(step.input_qty)}
                </Check>
              ) : null}
              {rows.length ? <Check ok={fails === 0}>{fails === 0 ? `All ${rows.length} parameters within tolerance` : `${fails} of ${rows.length} parameters failed`}</Check> : <Check ok>No QC readings on this report</Check>}
              {auto ? <Check ok>{auto} reading(s) auto-filled (AUTO · nominal) · {rows.length - auto} entered</Check> : null}
            </ul>
          </Card>
          <Card title="Sign-off" description="Prepared → Reviewed → Approved, each by a different person">
            <ApprovalPanel doc={x} compact onRevised={(n) => router.push(d(`/editor/${n.id}`))} />
          </Card>
          <Card title="Saved to"><p className="m-0 text-[12.5px] text-fg-2">/{x.folder_path.join(" / ")}</p></Card>
        </div>
      </div>
    </div>
  );
}
