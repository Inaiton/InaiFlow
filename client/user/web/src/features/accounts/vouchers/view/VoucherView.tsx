"use client";

import { CheckCircle2, Paperclip } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { Badge, Button, Card, ConfirmDialog, ErrorState, Hint, PageHeader, Skeleton, StatusBadge } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { useCan } from "@/core/permissions/Can";
import { useShortcutScope } from "@/core/shortcuts/registry";
import { useAccHref } from "../../lib/api-base";
import { inr } from "../../lib/format";
import { INVOICE_BASES, kindOf } from "../../lib/voucher-kinds";
import { useRBar } from "../../shell/rbar-context";
import { useCancelVoucher, usePrintVoucher, useVoucher } from "../api";
import { useAttachBill } from "../entry/attach";
import { BillDocument } from "./BillDocument";
import { EditLogSheet } from "./EditLogSheet";
import { EinvoicePanel } from "./EinvoicePanel";

/** /accounts/vouchers/[id] — saved voucher as a printable bill; print PDF, alter, cancel, edit log, e-invoice, attachments. */
export function VoucherView({ id }: { id: string }) {
  useShortcutScope("voucher");
  const router = useRouter();
  const href = useAccHref();
  const params = useSearchParams();
  const q = useVoucher(id);
  const print = usePrintVoucher();
  const cancel = useCancelVoucher();
  const attach = useAttachBill();
  const canWrite = useCan("accounts.vouchers", "WRITE");
  const canFull = useCan("accounts.vouchers", "FULL");
  const [logOpen, setLogOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const v = q.data;
  const kind = kindOf(v?.base_type);
  const editable = Boolean(v && kind && v.status !== "CANCELLED" && canWrite);
  const doPrint = () => v && print.mutate({ id: v.id, number: v.voucher_number });
  useRBar([
    { id: "print", combo: "alt+p", label: "Print (PDF)", run: doPrint, disabled: !v },
    { id: "alter", combo: "ctrl+e", label: "Alter", href: href(`/vouchers/${id}/edit`), disabled: !editable },
    { id: "cancel", combo: "alt+x", label: "Cancel voucher", run: () => setCancelOpen(true), disabled: !v || v.status === "CANCELLED" || !canFull },
    { id: "log", combo: "alt+l", label: "Edit log", run: () => setLogOpen(true) },
    { id: "attach", combo: "alt+v", label: "Attach bill", run: () => fileRef.current?.click(), disabled: !canWrite || !v },
    { id: "next", combo: kind?.combo ?? undefined, label: `New ${kind?.label ?? "voucher"}`, href: href(`/vouchers/new?type=${v?.base_type ?? "JOURNAL"}`), sep: true },
    { id: "daybook", combo: "alt+d", label: "Day book", href: href("/daybook") },
    { id: "quit", combo: "escape", label: "Back", run: () => router.back() },
  ], "voucher");
  if (q.isPending) return <Skeleton className="h-[600px] w-full" />;
  if (q.isError || !v) return <ErrorState message={describeError(q.error)} onRetry={() => void q.refetch()} />;
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Accounts", href: href("") }, { label: "Day book", href: href("/daybook") }, { label: v.voucher_number }]}
        title={<span className="flex items-center gap-2">{v.voucher_type_name} {v.voucher_number} <StatusBadge status={v.status} /></span>}
        description={`${v.party_name ? `${v.party_name} · ` : ""}${inr(v.total_amount)}${v.linked_period_run_id ? " · linked to a period run" : ""}`}
        actions={<>
          <Button variant="ghost" onClick={() => setLogOpen(true)}>Edit log</Button>
          {editable ? <Button asChild variant="secondary"><Link href={href(`/vouchers/${id}/edit`)}>Alter</Link></Button> : null}
          {canFull && v.status !== "CANCELLED" ? <Button variant="destructive" onClick={() => setCancelOpen(true)}>Cancel</Button> : null}
          <Button variant="primary" loading={print.isPending} onClick={doPrint}>Print PDF</Button>
        </>}
      />
      {params.get("saved") ? (
        <Hint tone="sky" title={<span className="flex items-center gap-1.5"><CheckCircle2 className="size-4 text-success" aria-hidden />Voucher saved</span>}
          action={<Button asChild size="sm" variant="secondary"><Link href={href(`/vouchers/new?type=${v.base_type}`)}>Next {kind?.label.toLowerCase() ?? "voucher"}</Link></Button>}>
          {v.voucher_number} posted to books{v.status !== "REGULAR" ? ` as ${v.status.toLowerCase().replace("_", "-")} (not in reports)` : ""}.
        </Hint>
      ) : null}
      {v.status === "CANCELLED" && v.cancel_reason ? <Hint tone="danger" title="Cancelled">{v.cancel_reason}</Hint> : null}
      <div className="grid items-start gap-4 2xl:grid-cols-[minmax(0,1fr)_320px]">
        <BillDocument v={v} />
        <div className="flex flex-col gap-4">
          {INVOICE_BASES.includes(v.base_type) && v.base_type !== "PURCHASE" && v.status !== "CANCELLED" ? <EinvoicePanel voucherId={v.id} /> : null}
          <Card title="Attachments" description="Scanned bills filed in Documents">
            <input ref={fileRef} type="file" className="sr-only" aria-label="Attach bill" accept="application/pdf,image/*"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) attach.mutate({ voucherId: v.id, voucherDate: v.voucher_date, file: f, source: f.type.startsWith("image/") ? "CAMERA_SCAN" : "FILE_UPLOAD" }); e.target.value = ""; }} />
            <ul className="flex flex-col gap-1.5 text-[12.5px]">
              {v.attachments.map((a) => <li key={a.id} className="flex items-center gap-1.5"><Paperclip className="size-3.5 text-fg-muted" aria-hidden />{a.title}<Badge>{a.file_mime_type?.split("/")[1] ?? "file"}</Badge></li>)}
              {v.attachments.length === 0 ? <li className="text-fg-muted">No bill attached.</li> : null}
            </ul>
            {canWrite ? <Button size="sm" variant="secondary" className="mt-2" loading={attach.isPending} onClick={() => fileRef.current?.click()}><Paperclip />Attach bill</Button> : null}
          </Card>
        </div>
      </div>
      <EditLogSheet id={v.id} number={v.voucher_number} open={logOpen} onOpenChange={setLogOpen} />
      <ConfirmDialog open={cancelOpen} onOpenChange={setCancelOpen} title={`Cancel ${v.voucher_number}?`}
        description="Keeps the number and removes it from every report. The reason is saved in the immutable edit log. Cancel any e-Invoice separately."
        requireReason reasonLabel="Reason (required)" confirmText={v.voucher_number} destructive confirmLabel="Cancel voucher" loading={cancel.isPending}
        onConfirm={async (reason) => { await cancel.mutateAsync({ id: v.id, reason }); setCancelOpen(false); }} />
    </>
  );
}
