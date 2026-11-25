"use client";

import { useState } from "react";
import { Button, DatePicker, Dialog, DialogContent, Field, FieldRow } from "@/components/ui";
import { monthsOfFy, monthLabel } from "@/core/dates";
import { monthPeriod, type Period } from "../lib/period";

/** F2 — change period (Tally "Alt+F2"). `single` = one "as on" date. */
export function PeriodDialog({ open, onOpenChange, period, fy, onApply, single }: {
  open: boolean; onOpenChange: (o: boolean) => void; period: Period; fy: { start: string; end: string; label: string }; onApply: (p: Period) => void; single?: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? <Body period={period} fy={fy} single={single} onApply={(p) => { onApply(p); onOpenChange(false); }} onCancel={() => onOpenChange(false)} /> : null}
    </Dialog>
  );
}

function Body({ period, fy, single, onApply, onCancel }: { period: Period; fy: { start: string; end: string; label: string }; single?: boolean; onApply: (p: Period) => void; onCancel: () => void }) {
  const [from, setFrom] = useState(period.from);
  const [to, setTo] = useState(period.to);
  const valid = Boolean(from && to && from <= to);
  return (
    <DialogContent
      title={single ? "Change date" : "Change period"}
      description={`${fy.label} · press Enter to apply`}
      size="sm"
      footer={<><Button variant="ghost" onClick={onCancel}>Cancel</Button><Button variant="primary" disabled={!valid} onClick={() => onApply({ from: single ? fy.start : from, to })}>Apply</Button></>}
    >
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (valid) onApply({ from: single ? fy.start : from, to }); }}>
        <FieldRow>
          {single ? null : <Field label="From"><DatePicker value={from} onValueChange={(v) => setFrom(v ?? "")} /></Field>}
          <Field label={single ? "As on" : "To"}><DatePicker value={to} onValueChange={(v) => setTo(v ?? "")} /></Field>
        </FieldRow>
        <div className="flex flex-wrap gap-1.5">
          <Button size="sm" variant="secondary" onClick={() => { setFrom(fy.start); setTo(fy.end); }}>Full FY</Button>
          {monthsOfFy(fy).map((m) => (
            <Button key={m} size="sm" variant="ghost" onClick={() => { const p = monthPeriod(m); setFrom(p.from); setTo(p.to); }}>{monthLabel(m)}</Button>
          ))}
        </div>
        <button type="submit" hidden />
      </form>
    </DialogContent>
  );
}
