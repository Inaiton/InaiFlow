"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, Card, ConfirmDialog, ErrorState, Field, KeyValue, NativeSelect, PageHeader, Skeleton, Textarea } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { formatDate, formatDateTime } from "@/core/dates";
import { formatQty } from "@/core/money";
import { useCan } from "@/core/permissions/Can";
import { useCloseNcr, useNcr, useUpdateNcr } from "../../api/iso";
import { useMemberLookup } from "../../api/lookups";
import { useOpsPath } from "../../paths";
import { NcrBadge } from "../shared/status";

/** /operations/iso-compliance/ncr/[ncrId] — root cause, CAPA, owner, verification & close (design Ops-ISO-NCR*). */
export function NcrDetail({ ncrId }: { ncrId: string }) {
  const ncr = useNcr(ncrId);
  if (ncr.isError) return <ErrorState message={describeError(ncr.error)} onRetry={() => void ncr.refetch()} />;
  if (!ncr.data) return <Skeleton className="h-96" />;
  return <NcrForm key={ncr.data.id + ncr.data.status} ncr={ncr.data} />;
}

function NcrForm({ ncr }: { ncr: Schemas["NcrOut"] }) {
  const p = useOpsPath();
  const canWrite = useCan("operations.iso_compliance", "WRITE");
  const canClose = useCan("operations.iso_compliance", "FULL");
  const members = useMemberLookup();
  const update = useUpdateNcr(ncr.id);
  const close = useCloseNcr(ncr.id);
  const closed = ncr.status === "VERIFIED_CLOSED";
  const [f, setF] = useState({ defect: ncr.defect_description, rca: ncr.root_cause_analysis ?? "", ca: ncr.corrective_action ?? "", pa: ncr.preventive_action ?? "", owner: ncr.assigned_to ?? "" });
  const [closing, setClosing] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));
  const save = () => update.mutateAsync({
    defect_description: f.defect, root_cause_analysis: f.rca || null, corrective_action: f.ca || null, preventive_action: f.pa || null,
    assigned_to: f.owner || null, status: ncr.status === "OPEN" && (f.rca || f.ca) ? "INVESTIGATING" : undefined,
  });
  const ro = closed || !canWrite;
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        crumbs={[{ label: "Operations", href: p() }, { label: "ISO compliance", href: p("/iso-compliance?tab=ncr") }, { label: ncr.ncr_number }]}
        title={<span className="flex items-center gap-2">{ncr.ncr_number} <NcrBadge status={ncr.status} /></span>}
        description={`${ncr.source === "AUTO_QC" ? "Raised automatically at a QC gate" : "Raised manually"} · ${formatDate(ncr.created_at)}`}
        actions={!closed ? (
          <>
            {canWrite ? <Button loading={update.isPending} onClick={() => void save()}>Save</Button> : null}
            {canClose ? <Button variant="primary" disabled={!f.ca.trim()} title={f.ca.trim() ? undefined : "Record a corrective action first"} onClick={() => setClosing(true)}>Verify & close</Button> : null}
          </>
        ) : null}
      />
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card title="Investigation" description="Root cause, then the fix and how you prevent it next time">
          <fieldset disabled={ro} className="flex flex-col gap-3.5">
            <Field label="Defect"><Textarea value={f.defect} onChange={set("defect")} /></Field>
            <Field label="Root cause analysis" hint="5-Why or fishbone summary"><Textarea value={f.rca} onChange={set("rca")} /></Field>
            <Field label="Corrective action"><Textarea value={f.ca} onChange={set("ca")} /></Field>
            <Field label="Preventive action"><Textarea value={f.pa} onChange={set("pa")} /></Field>
          </fieldset>
        </Card>
        <Card title="Details">
          <KeyValue rows={[
            ["Run", ncr.period_run_id ? <Link key="r" href={p(`/runs/${ncr.period_run_id}`)}>{ncr.run_title}</Link> : "—"],
            ["Step", ncr.step_name ?? "—"],
            ["Rejected qty", formatQty(ncr.rejected_qty)],
            ...(closed ? [["Closed by", `${ncr.closed_by_name ?? "—"} · ${formatDateTime(ncr.closed_at)}`] as [string, string], ["Verification", ncr.verification_notes ?? "—"] as [string, string]] : []),
          ]} />
          <Field label="Owner">
            {members.data ? (
              <NativeSelect disabled={ro} value={f.owner} onChange={set("owner")}>
                <option value="">Unassigned</option>
                {members.data.map((m) => <option key={m.user_id} value={m.user_id}>{m.full_name}</option>)}
              </NativeSelect>
            ) : <span className="text-[13px] text-fg-2">{ncr.assigned_to_name ?? "Unassigned"}</span>}
          </Field>
        </Card>
      </div>
      <ConfirmDialog open={closing} onOpenChange={setClosing} title={`Close ${ncr.ncr_number}?`} description="Confirm the corrective action worked. The NCR becomes read-only."
        confirmLabel="Verify & close" loading={close.isPending} requireReason reasonLabel="Verification notes (e.g. next 3 batches checked)"
        onConfirm={async (notes) => { await save(); await close.mutateAsync({ verification_notes: notes }); setClosing(false); }} />
    </div>
  );
}
