"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { describeError } from "@/core/api/error-messages";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { Button, Card, Hint, PageHeader, Stepper } from "@/components/ui";
import { useCreateOrg } from "@/features/me/api";
import { defaultOrgValues, orgCreateSchema, STEP_FIELDS, suggestSlug, toOrgCreateIn } from "../schema";
import { StepEssentials } from "./StepEssentials";
import { StepFinancial, useSlugAvailability } from "./StepFinancial";
import { StepReview } from "./StepReview";
import { StepStatutory } from "./StepStatutory";

const STEPS = [
  { title: "Essentials", description: "Name, address, contact" },
  { title: "Tax registration", description: "GST, PAN, MSME" },
  { title: "Financial year", description: "FY, slug, industry" },
  { title: "Review", description: "Confirm & create" },
];

const NEXT_UP = ["Seeds 28 Tally account groups & GST ledgers", "Creates 6 roles — you become Org owner", "Adds ISO 9001 workflow templates", "Builds the locked FY folder tree"];

/** /organizations/new — multi-step org creation (design: Org-Create-*.dc.html). */
export function OrgCreateWizard() {
  const router = useRouter();
  const create = useCreateOrg();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const form = useZodForm(orgCreateSchema, { defaultValues: defaultOrgValues() });
  const slugCheck = useSlugAvailability(form.watch("workspace_slug"));

  const next = async () => {
    if (step === 0 && !form.getValues("workspace_slug")) form.setValue("workspace_slug", suggestSlug(form.getValues("legal_name")));
    const ok = await form.trigger(STEP_FIELDS[step] ?? []);
    if (!ok) return;
    if (step === 2 && slugCheck.data === false) {
      form.setError("workspace_slug", { message: "That slug is already taken" });
      return;
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const submit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const org = await create.mutateAsync(toOrgCreateIn(values));
      router.replace(`/o/${org.workspace_slug}?welcome=1`);
    } catch (e) {
      if (applyServerErrors(form, e)) {
        const firstBad = STEP_FIELDS.findIndex((fields) => fields.some((f) => form.getFieldState(f).invalid));
        if (firstBad >= 0) setStep(firstBad);
      }
      setError(describeError(e));
    }
  }, () => setError("Some fields need attention — check the earlier steps."));

  return (
    <>
      <PageHeader crumbs={[{ label: "Personal space", href: "/me" }, { label: "Create organization" }]} title="Create organization" description={`Step ${step + 1} of ${STEPS.length} · ${STEPS[step]?.description}`} />
      <Stepper steps={STEPS} current={step} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <Card title={STEPS[step]?.title}>
          <form onSubmit={(e) => { e.preventDefault(); if (step === STEPS.length - 1) void submit(); else void next(); }} noValidate className="flex flex-col gap-5">
            {step === 0 ? <StepEssentials form={form} /> : step === 1 ? <StepStatutory form={form} /> : step === 2 ? <StepFinancial form={form} /> : <StepReview form={form} />}
            {error ? <Hint tone="danger">{error}</Hint> : null}
            <div className="flex justify-between gap-2 border-t border-line pt-4">
              <Button variant="secondary" onClick={() => (step === 0 ? router.push("/me/organizations") : setStep(step - 1))}>{step === 0 ? "Cancel" : "Back"}</Button>
              <Button type="submit" variant="primary" loading={create.isPending}>{step === STEPS.length - 1 ? "Create organization" : "Continue"}</Button>
            </div>
          </form>
        </Card>
        <Card title="What happens next" description="On create we will">
          <ul className="flex flex-col gap-2 text-[13px] text-fg-3">
            {NEXT_UP.map((n) => <li key={n} className="flex gap-2"><span className="mt-1.5 size-1.5 flex-none rounded-[2px] bg-primary" aria-hidden />{n}</li>)}
          </ul>
        </Card>
      </div>
    </>
  );
}
