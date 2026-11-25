"use client";

import { Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Button, DataTable, DatePicker, Dialog, DialogContent, ErrorState, EmptyState, Field, FieldRow, Input, NativeSelect, Segmented, type ColumnDef } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { formatDate, todayIso } from "@/core/dates";
import { useCan } from "@/core/permissions/Can";
import { DocumentPicker } from "@/features/documents/public";
import { useCalibrate, useInstruments, useSaveInstrument } from "../../api/iso";
import { InstrumentBadge } from "../shared/status";

type Instrument = Schemas["InstrumentOut"];

/** Calibration register (design Ops-ISO-Calibration / Instrument*). Expired gauges block QC entry. */
export function CalibrationTab() {
  const [status, setStatus] = useState("");
  const list = useInstruments(status || undefined);
  const canWrite = useCan("operations.iso_compliance", "WRITE");
  const [edit, setEdit] = useState<Instrument | "new" | null>(null);
  const [cal, setCal] = useState<Instrument | null>(null);
  const cols = useMemo<ColumnDef<Instrument, unknown>[]>(() => [
    { header: "Instrument", accessorKey: "instrument_code", cell: ({ row }) => <span className="flex flex-col"><span className="font-semibold text-fg">{row.original.instrument_code}</span><span className="text-xs text-fg-muted">{row.original.name}</span></span> },
    { header: "Location", cell: ({ row }) => row.original.location ?? "—" },
    { header: "Range / least count", cell: ({ row }) => [row.original.range_spec, row.original.least_count].filter(Boolean).join(" · ") || "—" },
    { header: "Last calibrated", cell: ({ row }) => formatDate(row.original.last_calibrated_date) },
    { header: "Next due", cell: ({ row }) => `${formatDate(row.original.next_due_date)}${row.original.days_to_due >= 0 ? ` · ${row.original.days_to_due} d` : ""}` },
    { header: "Status", cell: ({ row }) => <InstrumentBadge status={row.original.status} /> },
    { id: "act", header: "", cell: ({ row }) => canWrite ? (
      <span className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
        <Button size="sm" variant={row.original.status === "VALID" ? "ghost" : "primary"} onClick={() => setCal(row.original)}>Record calibration</Button>
      </span>
    ) : null },
  ], [canWrite]);
  return (
    <div className="flex flex-col gap-3 pt-2">
      <div className="flex flex-wrap items-center gap-2">
        <Segmented aria-label="Status" value={status} onChange={setStatus} options={[{ value: "", label: "All" }, { value: "DUE_SOON", label: "Due soon" }, { value: "EXPIRED", label: "Expired" }, { value: "VALID", label: "Valid" }]} />
        <span className="flex-1" />
        {canWrite ? <Button onClick={() => setEdit("new")}><Plus /> Add instrument</Button> : null}
      </div>
      {list.isError ? <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} /> : (
        <DataTable aria-label="Instruments" columns={cols} data={list.data} loading={list.isPending} getRowId={(i) => i.id} onRowClick={canWrite ? (i) => setEdit(i) : undefined}
          empty={<EmptyState title="No instruments" description="Add gauges, micrometers and test equipment with their calibration due dates." />} />
      )}
      {edit ? <InstrumentDialog key={edit === "new" ? "new" : edit.id} instrument={edit === "new" ? undefined : edit} onClose={() => setEdit(null)} /> : null}
      {cal ? <CalibrateDialog key={cal.id} instrument={cal} onClose={() => setCal(null)} /> : null}
    </div>
  );
}

function InstrumentDialog({ instrument, onClose }: { instrument?: Instrument; onClose: () => void }) {
  const save = useSaveInstrument(instrument?.id);
  const [f, setF] = useState({
    instrument_code: instrument?.instrument_code ?? "", name: instrument?.name ?? "", location: instrument?.location ?? "", range_spec: instrument?.range_spec ?? "",
    least_count: instrument?.least_count ?? "", last: instrument?.last_calibrated_date ?? todayIso(), next: instrument?.next_due_date ?? "", cert: instrument?.certificate_doc_id ?? null,
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));
  const ready = f.instrument_code.trim() && f.name.trim() && f.last && f.next && f.next >= f.last;
  const submit = async () => {
    await save.mutateAsync({ instrument_code: f.instrument_code.trim(), name: f.name.trim(), location: f.location || null, range_spec: f.range_spec || null, least_count: f.least_count || null, last_calibrated_date: f.last, next_due_date: f.next, certificate_doc_id: f.cert });
    onClose();
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={instrument ? `Edit ${instrument.instrument_code}` : "Add instrument"}
        footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!ready} loading={save.isPending} onClick={() => void submit()}>Save</Button></>}>
        <div className="flex flex-col gap-3.5">
          <FieldRow>
            <Field label="Code" required><Input value={f.instrument_code} onChange={set("instrument_code")} placeholder="MC-07" /></Field>
            <Field label="Name" required><Input value={f.name} onChange={set("name")} placeholder="Outside micrometer 25–50" /></Field>
          </FieldRow>
          <FieldRow>
            <Field label="Range"><Input value={f.range_spec} onChange={set("range_spec")} /></Field>
            <Field label="Least count"><Input value={f.least_count} onChange={set("least_count")} /></Field>
          </FieldRow>
          <Field label="Location"><Input value={f.location} onChange={set("location")} /></Field>
          <FieldRow>
            <Field label="Last calibrated" required><DatePicker value={f.last} onValueChange={(v) => setF((s) => ({ ...s, last: v ?? "" }))} /></Field>
            <Field label="Next due" required error={f.next && f.next < f.last ? "Must be after the last calibration" : undefined}><DatePicker value={f.next} onValueChange={(v) => setF((s) => ({ ...s, next: v ?? "" }))} /></Field>
          </FieldRow>
          <Field label="Certificate"><DocumentPicker value={f.cert} onChange={(cert) => setF((s) => ({ ...s, cert }))} /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CalibrateDialog({ instrument, onClose }: { instrument: Instrument; onClose: () => void }) {
  const calibrate = useCalibrate(instrument.id);
  const [on, setOn] = useState(todayIso());
  const [next, setNext] = useState("");
  const [cert, setCert] = useState<string | null>(null);
  const [preset, setPreset] = useState("");
  const applyPreset = (months: string) => {
    setPreset(months);
    if (!months) return;
    const d = new Date(`${on}T00:00:00`);
    d.setMonth(d.getMonth() + Number(months));
    setNext(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`);
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={`Record calibration · ${instrument.instrument_code}`} description="Attach the certificate so it shows in the audit pack."
        footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!on || !next || next <= on} loading={calibrate.isPending}
          onClick={async () => { await calibrate.mutateAsync({ calibrated_on: on, next_due_date: next, certificate_doc_id: cert }); onClose(); }}>Save calibration</Button></>}>
        <div className="flex flex-col gap-3.5">
          <FieldRow>
            <Field label="Calibrated on" required><DatePicker value={on} onValueChange={(v) => setOn(v ?? "")} /></Field>
            <Field label="Interval">
              <NativeSelect value={preset} onChange={(e) => applyPreset(e.target.value)}>
                <option value="">Pick a date</option><option value="3">3 months</option><option value="6">6 months</option><option value="12">12 months</option>
              </NativeSelect>
            </Field>
          </FieldRow>
          <Field label="Next due" required><DatePicker value={next} onValueChange={(v) => { setNext(v ?? ""); setPreset(""); }} /></Field>
          <Field label="Certificate"><DocumentPicker value={cert} onChange={setCert} /></Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}
