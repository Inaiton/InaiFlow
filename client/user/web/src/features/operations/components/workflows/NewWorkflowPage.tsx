"use client";

import { Check } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button, Card, Combobox, Field, FieldRow, Input, PageHeader, Skeleton } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useOpsItems } from "../../api/items";
import { useCreateWorkflow, useWorkflowLibrary } from "../../api/workflows";
import { useOpsPath } from "../../paths";

/** /operations/workflows/new — pick a template (or blank), name it, link an item (design Ops-WF-New). */
export function NewWorkflowPage() {
  const p = useOpsPath();
  const router = useRouter();
  const params = useSearchParams();
  const lib = useWorkflowLibrary();
  const [template, setTemplate] = useState<string | null>(params.get("template"));
  const [name, setName] = useState("");
  const [itemId, setItemId] = useState<string | null>(params.get("item"));
  const [itemQ, setItemQ] = useState("");
  const items = useOpsItems({ q: itemQ || undefined, limit: 30, offset: 0 });
  const create = useCreateWorkflow();
  const chosen = lib.data?.find((t) => t.key === template);
  const finalName = name.trim() || chosen?.name || "";

  const submit = async () => {
    const out = await create.mutateAsync({ name: finalName, stock_item_id: itemId, from_library_key: template, iso_clause_ref: chosen?.iso_clause_ref ?? null });
    router.push(p(`/workflows/${out.id}`));
  };
  const options = [{ key: null, name: "Blank canvas", description: "Start with an empty flow and add steps yourself.", steps: 0 }, ...(lib.data ?? []).map((t) => ({ key: t.key as string | null, name: t.name, description: t.description, steps: t.graph_definition.nodes.length }))];
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        crumbs={[{ label: "Operations", href: p() }, { label: "Workflow studio", href: p("/workflows") }, { label: "New" }]}
        title="New workflow"
        description="Pick a starting point — you can change every step afterwards"
        actions={<><Button onClick={() => router.back()}>Cancel</Button><Button variant="primary" disabled={!finalName} loading={create.isPending} onClick={() => void submit()}>Create & open studio</Button></>}
      />
      <Card title="1 · Start from">
        {!lib.data ? <Skeleton className="h-28" /> : (
          <div role="radiogroup" aria-label="Template" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {options.map((o) => {
              const active = o.key === template;
              return (
                <button key={o.key ?? "blank"} type="button" role="radio" aria-checked={active} onClick={() => setTemplate(o.key)}
                  className={cn("flex flex-col gap-1 rounded-xl border px-4 py-3 text-left", active ? "border-primary bg-primary-tint" : "border-line hover:border-line-strong")}>
                  <span className="flex items-center gap-2 text-[13.5px] font-semibold text-fg">{active ? <Check className="size-4 text-primary" /> : null}{o.name}</span>
                  <span className="text-xs text-fg-muted">{o.description}</span>
                  {o.steps ? <span className="text-xs text-fg-muted">{o.steps} steps</span> : null}
                </button>
              );
            })}
          </div>
        )}
      </Card>
      <Card title="2 · Name and item">
        <FieldRow>
          <Field label="Workflow name" required hint={chosen && !name ? `Defaults to “${chosen.name}”` : undefined}>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={chosen?.name ?? "Flange machining"} />
          </Field>
          <Field label="Item it produces" hint="Optional — lets runs post stock and cost to this item">
            <Combobox value={itemId} onValueChange={setItemId} onSearch={setItemQ} loading={items.isFetching && !items.data}
              options={(items.data?.items ?? []).map((i) => ({ value: i.id, label: i.name, hint: i.sku_code ?? i.uom_primary }))} placeholder="Choose an item" />
          </Field>
        </FieldRow>
      </Card>
    </div>
  );
}
