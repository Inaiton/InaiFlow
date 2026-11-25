"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Controller } from "react-hook-form";
import { qk } from "@/core/query-keys";
import { DatePicker, Field, FieldRow, Input, Select, Spinner } from "@/components/ui";
import { checkSlug } from "@/features/me/api";
import { INDUSTRIES, SLUG_RE } from "../schema";
import type { OrgForm } from "./types";

function useDebounced<T>(value: T, ms = 400): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Live slug availability via GET /organizations/check-slug. */
export function useSlugAvailability(slug: string) {
  const debounced = useDebounced(slug.trim().toLowerCase());
  return useQuery({ queryKey: qk.me("check-slug", debounced), queryFn: () => checkSlug(debounced), enabled: SLUG_RE.test(debounced), staleTime: 30_000, meta: { silentError: true } });
}

export function StepFinancial({ form }: { form: OrgForm }) {
  const { errors } = form.formState;
  const slug = form.watch("workspace_slug");
  const avail = useSlugAvailability(slug);
  const slugHint = !SLUG_RE.test(slug) ? "Your workspace address" : avail.isFetching ? <Spinner className="size-3.5" /> : avail.data === true ? (
    <span className="flex items-center gap-1 text-success-text"><CheckCircle2 className="size-3.5" /> Available</span>
  ) : avail.data === false ? (
    <span className="flex items-center gap-1 text-danger-text"><XCircle className="size-3.5" /> Already taken</span>
  ) : "Your workspace address";
  return (
    <div className="flex flex-col gap-4">
      <FieldRow>
        <Field label="Financial year begins" hint="Indian FY: 1 April" error={errors.fy_begins_from?.message} required>
          <Controller control={form.control} name="fy_begins_from" render={({ field }) => <DatePicker value={field.value} onValueChange={(v) => field.onChange(v ?? "")} />} />
        </Field>
        <Field label="Books beginning from" hint="First date you’ll post vouchers" error={errors.books_beginning_from?.message} required>
          <Controller control={form.control} name="books_beginning_from" render={({ field }) => <DatePicker value={field.value} onValueChange={(v) => field.onChange(v ?? "")} />} />
        </Field>
        <Field label="Workspace slug" hint={slugHint} error={errors.workspace_slug?.message} required>
          <Input prefix="/o/" {...form.register("workspace_slug")} />
        </Field>
        <Field label="Workspace code" hint="Generated on create · share it for join requests"><Input value="ORG-····" readOnly /></Field>
        <Field label="Industry / manufacturing type" hint="Seeds default ledgers, UoMs and ISO workflow templates" required>
          <Controller control={form.control} name="industry_type" render={({ field }) => <Select value={field.value} onValueChange={field.onChange} options={INDUSTRIES} />} />
        </Field>
        <Field label="ISO standard" hint="Optional"><Input {...form.register("iso_standard")} /></Field>
      </FieldRow>
    </div>
  );
}
