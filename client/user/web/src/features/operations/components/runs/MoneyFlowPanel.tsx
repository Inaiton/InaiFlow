"use client";

import { Link2, Plus, Unlink, Wallet } from "lucide-react";
import { useState } from "react";
import { Button, Card, ConfirmDialog, KpiCard, KpiGrid } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { formatDate } from "@/core/dates";
import { formatMoney, formatQty } from "@/core/money";
import { useCan } from "@/core/permissions/Can";
import { useUnlinkVoucher } from "../../api/runs";
import { LinkVoucherDialog, PostingDialog } from "./MoneyDialogs";

type Line = Schemas["MoneyFlowLine"];

/** Dr/Cr money flow of a run with unit cost (dossier page 2), posting and voucher linking. */
export function MoneyFlowPanel({ run }: { run: Schemas["RunOut"] }) {
  const canWrite = useCan("operations.runs_accounting", "WRITE") && run.status !== "COMPLETED" && run.status !== "CANCELLED";
  const [dialog, setDialog] = useState<"post" | "link" | null>(null);
  const [unlinkId, setUnlinkId] = useState<string | null>(null);
  const unlink = useUnlinkVoucher(run.id);
  const m = run.money_flow;
  const step = (id: string | null) => run.steps.find((s) => s.id === id)?.step_name;
  const lines = (title: string, rows: Line[], total: string) => (
    <div className="flex min-w-0 flex-col gap-1.5">
      <h3 className="m-0 flex justify-between text-[13px] font-semibold text-fg"><span>{title}</span><span className="tabular">{formatMoney(total)}</span></h3>
      {rows.length === 0 ? <p className="m-0 text-xs text-fg-muted">Nothing yet</p> : rows.map((l, i) => (
        <div key={`${l.voucher_id ?? "x"}-${i}`} className="flex items-center gap-2 rounded-lg bg-canvas px-2.5 py-1.5 text-[12.5px]">
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-fg">{l.particulars}</span>
            <span className="truncate text-[11px] text-fg-muted">{l.source.replace(/_/g, " ").toLowerCase()} · {l.voucher_number ?? "—"} · {formatDate(l.date)}{step(l.step_id) ? ` · ${step(l.step_id)}` : ""}</span>
          </span>
          <span className="tabular font-medium text-fg">{formatMoney(l.amount)}</span>
          {canWrite && l.voucher_id ? <Button size="icon-sm" variant="ghost" aria-label="Unlink voucher" onClick={() => setUnlinkId(l.voucher_id)}><Unlink /></Button> : null}
        </div>
      ))}
    </div>
  );
  return (
    <Card
      title="Money flow"
      description="Raw material + direct expenses + labour − scrap and sales credits"
      actions={canWrite ? <><Button size="sm" onClick={() => setDialog("link")}><Link2 /> Link voucher</Button><Button size="sm" onClick={() => setDialog("post")}><Plus /> Post Dr / Cr</Button></> : null}
    >
      <KpiGrid>
        <KpiCard title="Net run cost" value={formatMoney(m.net_cost)} icon={Wallet} tone="orange" caption={`${formatMoney(m.total_debit)} Dr − ${formatMoney(m.total_credit)} Cr`} />
        <KpiCard title="Unit cost" value={formatMoney(m.unit_cost)} icon={Wallet} tone="teal" caption={`over ${formatQty(m.accepted_qty)} accepted`} />
      </KpiGrid>
      <div className="grid gap-4 md:grid-cols-2">
        {lines("Debits (Dr)", m.debits, m.total_debit)}
        {lines("Credits (Cr)", m.credits, m.total_credit)}
      </div>
      <PostingDialog open={dialog === "post"} onOpenChange={(o) => setDialog(o ? "post" : null)} run={run} />
      <LinkVoucherDialog open={dialog === "link"} onOpenChange={(o) => setDialog(o ? "link" : null)} run={run} />
      <ConfirmDialog open={Boolean(unlinkId)} onOpenChange={(o) => !o && setUnlinkId(null)} title="Unlink this voucher?" description="The voucher stays in Accounts; it just stops counting toward this run." confirmLabel="Unlink"
        loading={unlink.isPending} onConfirm={async () => { if (unlinkId) await unlink.mutateAsync(unlinkId); setUnlinkId(null); }} />
    </Card>
  );
}
