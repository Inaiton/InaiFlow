"use client";

import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Spinner } from "@/components/ui/states";
import { errorMessage } from "@/lib/api/errors";
import type { Schemas } from "@/lib/api/client";
import { useCreatePlan, useUpdatePlan } from "./api";
import { MODULE_FLAGS, planFormSchema, type PlanFormValues } from "./schemas";

const trimDec = (s: string) => s.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");

function defaults(p: Schemas["PlanOut"] | null): PlanFormValues {
  return {
    plan_code: p?.plan_code ?? "",
    name: p?.name ?? "",
    monthly_price_inr: p ? trimDec(p.monthly_price_inr) : "",
    annual_price_inr: p ? trimDec(p.annual_price_inr) : "",
    max_internal_seats: p?.max_internal_seats ?? 5,
    max_external_collaborators: p?.max_external_collaborators ?? 2,
    max_storage_gb: p?.max_storage_gb ?? 10,
    enabled_modules: { ...Object.fromEntries(MODULE_FLAGS.map(([k]) => [k, false])), ...(p?.enabled_modules ?? {}) },
    is_active: p?.is_active ?? true,
    reason: "",
  };
}

export function PlanFormDialog({ plan, onClose }: { plan: Schemas["PlanOut"] | null; onClose: () => void }) {
  const create = useCreatePlan();
  const update = useUpdatePlan();
  const form = useForm<PlanFormValues>({ resolver: zodResolver(planFormSchema), defaultValues: defaults(plan) });
  const e = form.formState.errors;
  const pending = create.isPending || update.isPending;

  const submit = form.handleSubmit((v) => {
    const done = { onSuccess: () => (toast.success(plan ? "Plan updated" : "Plan created"), onClose()), onError: (err: unknown) => toast.error(errorMessage(err)) };
    if (plan) {
      const { plan_code: _code, ...rest } = v;
      void _code;
      update.mutate({ id: plan.id, body: rest }, done);
    } else create.mutate(v, done);
  });

  const num = (name: "max_internal_seats" | "max_external_collaborators" | "max_storage_gb") => form.register(name, { setValueAs: (x: string) => (x === "" ? undefined : Number(x)) });

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={plan ? `Edit plan · ${plan.plan_code}` : "New plan"}
        description={plan ? `${plan.org_count} organization(s) on this plan — changes apply to them immediately.` : undefined}
        className="max-w-2xl"
        footer={
          <>
            <Button onClick={onClose}>Cancel</Button>
            <Button variant="primary" onClick={() => void submit()} disabled={pending}>
              {pending ? <Spinner /> : null} {plan ? "Save plan" : "Create plan"}
            </Button>
          </>
        }
      >
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Plan code" error={e.plan_code?.message}>
              <Input className="font-mono" disabled={!!plan} {...form.register("plan_code")} />
            </Field>
            <Field label="Name" error={e.name?.message}>
              <Input {...form.register("name")} />
            </Field>
            <Field label="Monthly price ₹ (excl. GST)" error={e.monthly_price_inr?.message}>
              <Input inputMode="decimal" {...form.register("monthly_price_inr")} />
            </Field>
            <Field label="Annual price ₹ (excl. GST)" error={e.annual_price_inr?.message}>
              <Input inputMode="decimal" {...form.register("annual_price_inr")} />
            </Field>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Internal seats" error={e.max_internal_seats?.message}>
              <Input type="number" min={0} {...num("max_internal_seats")} />
            </Field>
            <Field label="External collaborators" error={e.max_external_collaborators?.message}>
              <Input type="number" min={0} {...num("max_external_collaborators")} />
            </Field>
            <Field label="Storage (GB)" error={e.max_storage_gb?.message}>
              <Input type="number" min={0} {...num("max_storage_gb")} />
            </Field>
          </div>
          <div>
            <p className="mb-2 text-[13px] font-medium text-muted">Module feature flags</p>
            <div className="grid grid-cols-2 gap-2">
              {MODULE_FLAGS.map(([k, label]) => (
                <Controller
                  key={k}
                  control={form.control}
                  name={`enabled_modules.${k}`}
                  render={({ field }) => (
                    <label className="flex items-center justify-between rounded-md border border-line px-3 py-2 text-[13px]">
                      {label}
                      <Switch checked={!!field.value} onCheckedChange={field.onChange} aria-label={label} />
                    </label>
                  )}
                />
              ))}
            </div>
          </div>
          <Controller
            control={form.control}
            name="is_active"
            render={({ field }) => (
              <label className="flex items-center gap-2 text-[13px]">
                <Switch checked={field.value} onCheckedChange={field.onChange} aria-label="Active" /> Available for new subscriptions
              </label>
            )}
          />
          <Field label="Reason (recorded in platform audit)" error={e.reason?.message}>
            <Textarea className="min-h-16" {...form.register("reason")} placeholder="Why is this plan being created or changed?" />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}
