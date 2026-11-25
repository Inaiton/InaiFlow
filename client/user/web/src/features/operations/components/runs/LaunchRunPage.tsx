"use client";

import { CirclePlay } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button, Card, DatePicker, DecimalInput, EmptyState, Field, FieldRow, Hint, Input, NativeSelect, PageHeader, Skeleton, SwitchRow } from "@/components/ui";
import { monthKey, monthLabel, monthStart } from "@/core/dates";
import { isZero } from "@/core/money";
import { useOpsItem } from "../../api/items";
import { useCreateRun } from "../../api/runs";
import { useWorkflows } from "../../api/workflows";
import { useOpsPath } from "../../paths";

/** /operations/runs/new — launch a period run (design Ops-Run-Launch). */
export function LaunchRunPage() {
  const p = useOpsPath();
  const router = useRouter();
  const params = useSearchParams();
  const itemParam = params.get("item");
  const workflows = useWorkflows();
  const published = (workflows.data ?? []).filter((w) => w.status === "PUBLISHED" && (!itemParam || w.stock_item_id === itemParam || !w.stock_item_id));
  const [workflowId, setWorkflowId] = useState<string>(params.get("workflow") ?? "");
  const wf = published.find((w) => w.id === workflowId) ?? (published.length === 1 ? published[0] : undefined);
  const itemId = wf?.stock_item_id ?? itemParam;
  const item = useOpsItem(itemId);
  const [month, setMonth] = useState<string>(monthKey(new Date()));
  const [qty, setQty] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [startNow, setStartNow] = useState(true);
  const [key] = useState(() => crypto.randomUUID());
  const create = useCreateRun();
  const autoTitle = `${item.data?.name ?? wf?.stock_item_name ?? wf?.name ?? "Run"} – ${monthLabel(month)}`;
  const ready = Boolean(wf && qty && !isZero(qty));

  const submit = async () => {
    if (!wf || !qty) return;
    const run = await create.mutateAsync({ key, body: { workflow_id: wf.id, period_month: monthStart(month), planned_qty: qty, run_title: title.trim() || autoTitle, stock_item_id: itemId ?? null, start_now: startNow } });
    router.push(p(`/runs/${run.id}`));
  };

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        crumbs={[{ label: "Operations", href: p() }, { label: "Period runs", href: p("/runs") }, { label: "Launch" }]}
        title="Launch a period run"
        description="One workflow, one month, one planned quantity"
        actions={<><Button onClick={() => router.back()}>Cancel</Button><Button variant="primary" disabled={!ready} loading={create.isPending} onClick={() => void submit()}><CirclePlay /> Launch run</Button></>}
      />
      {!workflows.data ? <Skeleton className="h-48" /> : published.length === 0 ? (
        <EmptyState icon={CirclePlay} tone="indigo" title="Publish a workflow first" description="Runs follow a published workflow version." action={<Button asChild variant="primary"><Link href={p("/workflows")}>Open workflow studio</Link></Button>} />
      ) : (
        <Card>
          <Field label="Workflow" required hint={wf ? `v${wf.version} · ${wf.node_count} steps — the run keeps this exact version` : undefined}>
            <NativeSelect value={wf?.id ?? ""} onChange={(e) => setWorkflowId(e.target.value)}>
              <option value="" disabled>Choose a published workflow</option>
              {published.map((w) => <option key={w.id} value={w.id}>{w.name} · v{w.version}{w.stock_item_name ? ` · ${w.stock_item_name}` : ""}</option>)}
            </NativeSelect>
          </Field>
          <FieldRow>
            <Field label="Period" required><DatePicker mode="month" value={month} onValueChange={(v) => v && setMonth(v)} /></Field>
            <Field label="Planned quantity" required hint={item.data ? `In ${item.data.uom_primary}` : undefined}>
              <DecimalInput kind="qty" decimals={4} value={qty} onValueChange={setQty} placeholder="500" />
            </Field>
          </FieldRow>
          <Field label="Run title" hint="Used for the cost centre and the document folder"><Input value={title} placeholder={autoTitle} onChange={(e) => setTitle(e.target.value)} /></Field>
          <SwitchRow label="Start now" description="First step becomes active straight away" checked={startNow} onCheckedChange={setStartNow} />
          <Hint tone="sky">Launching creates a matching cost centre in Accounts and a folder under <strong>{monthLabel(month)} / Operations & Production Runs</strong>.</Hint>
        </Card>
      )}
    </div>
  );
}
