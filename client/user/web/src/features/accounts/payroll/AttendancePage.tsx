"use client";

import { Download, Split } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, Checkbox, DatePicker, Dialog, DialogContent, EmptyState, Input, NativeSelect, PageHeader } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { monthKey, monthLabel, todayIso } from "@/core/dates";
import { isDecimal } from "@/core/money";
import { useCan } from "@/core/permissions/Can";
import { QueryState } from "../components/QueryState";
import { PAYROLL_NAV, SubNav } from "../components/SubNav";
import { useDialogGuard } from "../components/dialog-guard";
import { useAccHref } from "../lib/api-base";
import { humanize } from "../lib/format";
import { allocationError } from "./alloc";
import { useAttendance, usePeriodRuns, usePullOperations, useSaveAttendance } from "./api";

type Row = Schemas["AttendanceRow"];
type Alloc = Schemas["RunAllocation"];

function AllocDialog({ row, month, onSave, onClose }: { row: Row; month: string; onSave: (a: Alloc[]) => void; onClose: () => void }) {
  useDialogGuard();
  const runs = usePeriodRuns(month);
  const [list, setList] = useState<Alloc[]>(row.run_allocations);
  const err = allocationError(list);
  return (
    <DialogContent title={`Run allocation · ${row.full_name}`} description="Share of this operator’s wages charged to each period run (direct labour cost)" size="md"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={Boolean(err)} onClick={() => onSave(list)}>Accept</Button></>}>
      <div className="flex flex-col gap-2">
        {list.map((a, i) => (
          <div key={i} className="grid grid-cols-[minmax(0,1fr)_110px_auto] gap-2">
            <NativeSelect aria-label="Period run" value={a.period_run_id} onChange={(e) => setList((l) => l.map((x, j) => (j === i ? { ...x, period_run_id: e.target.value } : x)))}>
              <option value="">{runs.isPending ? "Loading runs…" : "Choose period run"}</option>
              {(runs.data?.items ?? []).map((r) => <option key={r.id} value={r.id}>{r.run_title}</option>)}
            </NativeSelect>
            <Input aria-label="Share %" inputMode="decimal" value={a.share_pct} onChange={(e) => setList((l) => l.map((x, j) => (j === i ? { ...x, share_pct: e.target.value } : x)))} />
            <Button variant="ghost" onClick={() => setList((l) => l.filter((_, j) => j !== i))}>Remove</Button>
          </div>
        ))}
        <Button size="sm" variant="ghost" className="self-start" onClick={() => setList((l) => [...l, { period_run_id: "", share_pct: l.length ? "" : "100" }])}>+ Add run</Button>
        {runs.isError ? <p className="text-[12px] text-warning-text">Period runs need Operations read access.</p> : null}
        {err ? <p className="text-[12px] text-danger-text">{err}</p> : null}
      </div>
    </DialogContent>
  );
}

function Grid({ month, initial }: { month: string; initial: Schemas["AttendanceOut"] }) {
  const save = useSaveAttendance();
  const pull = usePullOperations();
  const canWrite = useCan("accounts.payroll_runs", "WRITE");
  const [rows, setRows] = useState<Row[]>(initial.rows);
  const [alloc, setAlloc] = useState<Row | null>(null);
  const set = (id: string, patch: Partial<Row>) => setRows((r) => r.map((x) => (x.employee_id === id ? { ...x, ...patch } : x)));
  const invalid = rows.some((r) => ![r.days_present, r.lop_days, r.overtime_hours, r.production_units].every(isDecimal));
  const submit = (finalizeAll = false) => save.mutate({ month, rows: rows.map((r) => ({ employee_id: r.employee_id, days_present: r.days_present, lop_days: r.lop_days, overtime_hours: r.overtime_hours, production_units: r.production_units, run_allocations: r.run_allocations, finalized: finalizeAll || r.finalized })) });
  const num = (r: Row, k: "days_present" | "lop_days" | "overtime_hours" | "production_units") => (
    <Input aria-label={`${humanize(k)} for ${r.full_name}`} inputMode="decimal" disabled={!canWrite || r.finalized} value={r[k]} onChange={(e) => set(r.employee_id, { [k]: e.target.value })} className="h-8 w-20 text-right tabular" />
  );
  if (rows.length === 0) return <EmptyState title="No active employees" description="Add employees first." />;
  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead><tr className="border-b border-line bg-subtle text-[11.5px] text-fg-muted">{["Employee", "Category", "Days in month", "Present", "LOP", "OT hrs", "Units", "Run allocation", "Finalized"].map((h) => <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>)}</tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.employee_id} className="border-b border-line/60">
              <td className="px-3 py-1.5"><span className="font-medium text-fg">{r.full_name}</span> <span className="text-[11.5px] text-fg-muted">{r.emp_code}</span></td>
              <td className="px-3">{humanize(r.employee_category)}</td><td className="px-3 tabular">{r.days_in_month}</td>
              <td className="px-3">{num(r, "days_present")}</td><td className="px-3">{num(r, "lop_days")}</td><td className="px-3">{num(r, "overtime_hours")}</td><td className="px-3">{num(r, "production_units")}</td>
              <td className="px-3">{r.employee_category === "SHOP_FLOOR_OPERATOR" ? <Button size="sm" variant="ghost" disabled={!canWrite || r.finalized} onClick={() => setAlloc(r)}><Split />{r.run_allocations.length ? `${r.run_allocations.length} run(s)` : "Allocate"}</Button> : "—"}</td>
              <td className="px-3"><Checkbox aria-label={`Finalize ${r.full_name}`} disabled={!canWrite} checked={r.finalized} onCheckedChange={(v) => set(r.employee_id, { finalized: v === true })} /></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {canWrite ? (
        <div className="flex flex-wrap justify-end gap-2 p-4">
          <Button variant="ghost" loading={pull.isPending} onClick={() => pull.mutate(month, { onSuccess: (d) => setRows(d.rows) })}><Download />Pull production from Operations</Button>
          <Button variant="secondary" disabled={invalid} loading={save.isPending} onClick={() => submit(true)}>Finalize all</Button>
          <Button variant="primary" disabled={invalid} loading={save.isPending} onClick={() => submit()}>Save attendance</Button>
        </div>
      ) : null}
      <Dialog open={Boolean(alloc)} onOpenChange={(o) => !o && setAlloc(null)}>
        {alloc ? <AllocDialog row={alloc} month={month} onClose={() => setAlloc(null)} onSave={(a) => { set(alloc.employee_id, { run_allocations: a }); setAlloc(null); }} /> : null}
      </Dialog>
    </>
  );
}

/** /accounts/payroll/attendance — monthly attendance, OT, production units and run allocation (design: Acc-Pay-Attendance). */
export function AttendancePage() {
  const href = useAccHref();
  const [month, setMonth] = useState(monthKey(todayIso()));
  const q = useAttendance(month);
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Payroll", href: href("/payroll") }, { label: "Attendance" }]} title="Attendance" description={`${monthLabel(month)} · finalize every employee before locking the pay run`}
        actions={<><div className="w-44"><DatePicker mode="month" aria-label="Month" value={month} onValueChange={(v) => v && setMonth(v)} /></div>{q.data?.all_finalized ? <Badge tone="success">All finalized</Badge> : null}</>} />
      <SubNav items={PAYROLL_NAV} />
      <Card padded={false}><QueryState q={q}>{(d) => <Grid key={`${month}-${q.dataUpdatedAt}`} month={month} initial={d} />}</QueryState></Card>
    </>
  );
}
