"use client";

import { QrCode } from "lucide-react";
import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Badge, Button, Card, ConfirmDialog, Dialog, DialogContent, Field, FieldRow, Input, NativeSelect, StatusBadge } from "@/components/ui";
import { formatDateTime } from "@/core/dates";
import { Can, useCan } from "@/core/permissions/Can";
import { QueryState } from "../../components/QueryState";
import { useDialogGuard } from "../../components/dialog-guard";
import { useEinvoice, useEinvoiceAction } from "../../taxation/api";

function Qr({ text }: { text: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    QRCode.toDataURL(text, { margin: 1, width: 132 }).then((u) => live && setSrc(u)).catch(() => setSrc(null));
    return () => { live = false; };
  }, [text]);
  // eslint-disable-next-line @next/next/no-img-element -- generated data URL
  return src ? <img src={src} alt="Signed QR code" className="size-[132px] rounded-md border border-line" /> : <QrCode className="size-10 text-fg-faint" />;
}

/** e-Invoice (IRN + signed QR) and e-Way bill for a sales/credit/debit note. Runs against the mock gateway in this build. */
export function EinvoicePanel({ voucherId }: { voucherId: string }) {
  const canRead = useCan("accounts.taxation", "READ");
  const q = useEinvoice(voucherId, canRead);
  const act = useEinvoiceAction(voucherId);
  const [cancel, setCancel] = useState(false);
  const [eway, setEway] = useState(false);
  if (!canRead) return null;
  return (
    <Card title="e-Invoice & e-Way bill" description={<span className="flex items-center gap-1.5">IRP · <Badge tone="warning">Mock gateway</Badge></span>}>
      <QueryState q={q} rows={2}>
        {(records) => {
          const irn = records.find((r) => r.kind === "IRN");
          const ewb = records.find((r) => r.kind === "EWAY");
          return (
            <div className="flex flex-col gap-3">
              {irn ? (
                <div className="flex gap-3">
                  {irn.signed_qr ? <Qr text={irn.signed_qr} /> : null}
                  <dl className="flex min-w-0 flex-col gap-1 text-[12.5px]">
                    <div className="flex items-center gap-2"><StatusBadge status={irn.status} /></div>
                    <div><dt className="text-fg-muted">IRN</dt><dd className="font-mono text-[11px] break-all">{irn.irn ?? "—"}</dd></div>
                    <div><dt className="text-fg-muted">Ack</dt><dd>{irn.ack_no ?? "—"}{irn.ack_date ? ` · ${formatDateTime(irn.ack_date)}` : ""}</dd></div>
                  </dl>
                </div>
              ) : <p className="text-[12.5px] text-fg-muted">No IRN yet. B2B invoices above the AATO threshold need an e-Invoice.</p>}
              {ewb ? <p className="text-[12.5px]">e-Way bill <span className="font-semibold tabular">{ewb.eway_bill_no}</span>{ewb.valid_until ? ` · valid till ${formatDateTime(ewb.valid_until)}` : ""} <StatusBadge status={ewb.status} /></p> : null}
              <Can permission="accounts.taxation" level="WRITE">
                <div className="flex flex-wrap gap-2">
                  {!irn || irn.status === "CANCELLED" ? <Button size="sm" variant="secondary" loading={act.isPending} onClick={() => act.mutate({ kind: "generate" })}>Generate IRN & QR</Button> : null}
                  {irn && irn.status !== "CANCELLED" ? <Can permission="accounts.taxation" level="FULL"><Button size="sm" variant="destructive" onClick={() => setCancel(true)}>Cancel IRN</Button></Can> : null}
                  {!ewb ? <Button size="sm" variant="secondary" onClick={() => setEway(true)}>Generate e-Way bill</Button> : null}
                </div>
              </Can>
            </div>
          );
        }}
      </QueryState>
      <ConfirmDialog open={cancel} onOpenChange={setCancel} title="Cancel e-Invoice?" description="Allowed within 24 hours of generation. The voucher itself stays; cancel it separately if needed."
        requireReason reasonLabel="Remarks" destructive confirmLabel="Cancel IRN" loading={act.isPending}
        onConfirm={async (r) => { await act.mutateAsync({ kind: "cancel", body: { reason_code: "2", remarks: r } }); setCancel(false); }} />
      <Dialog open={eway} onOpenChange={setEway}>{eway ? <EwayForm loading={act.isPending} onClose={() => setEway(false)} onSubmit={async (b) => { await act.mutateAsync({ kind: "eway", body: b }); setEway(false); }} /> : null}</Dialog>
    </Card>
  );
}

function EwayForm({ onSubmit, onClose, loading }: { onSubmit: (b: { transporter_id: string | null; transporter_name: string | null; vehicle_no: string | null; distance_km: number; transport_mode: string }) => void; onClose: () => void; loading: boolean }) {
  useDialogGuard();
  const [f, setF] = useState({ transporter_id: "", transporter_name: "", vehicle_no: "", distance_km: "", transport_mode: "ROAD" });
  const ok = /^\d+$/.test(f.distance_km);
  return (
    <DialogContent title="Generate e-Way bill" description="Part A from the invoice; Part B (vehicle) below" size="md"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!ok} loading={loading} onClick={() => onSubmit({ transporter_id: f.transporter_id || null, transporter_name: f.transporter_name || null, vehicle_no: f.vehicle_no || null, distance_km: Number(f.distance_km), transport_mode: f.transport_mode })}>Generate</Button></>}>
      <div className="flex flex-col gap-3">
        <FieldRow>
          <Field label="Transport mode"><NativeSelect value={f.transport_mode} onChange={(e) => setF({ ...f, transport_mode: e.target.value })}>{["ROAD", "RAIL", "AIR", "SHIP"].map((m) => <option key={m}>{m}</option>)}</NativeSelect></Field>
          <Field label="Distance (km)" required><Input inputMode="numeric" value={f.distance_km} onChange={(e) => setF({ ...f, distance_km: e.target.value })} /></Field>
        </FieldRow>
        <FieldRow>
          <Field label="Vehicle no."><Input value={f.vehicle_no} onChange={(e) => setF({ ...f, vehicle_no: e.target.value.toUpperCase() })} placeholder="TN38BX4471" /></Field>
          <Field label="Transporter GSTIN / ID"><Input value={f.transporter_id} onChange={(e) => setF({ ...f, transporter_id: e.target.value.toUpperCase() })} /></Field>
        </FieldRow>
        <Field label="Transporter name"><Input value={f.transporter_name} onChange={(e) => setF({ ...f, transporter_name: e.target.value })} /></Field>
      </div>
    </DialogContent>
  );
}
