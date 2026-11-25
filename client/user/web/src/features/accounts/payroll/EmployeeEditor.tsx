"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Controller, useFieldArray, type Control, type UseFormRegister } from "react-hook-form";
import { Button, Card, DatePicker, ErrorState, Field, FieldRow, Input, NativeSelect, PageHeader, Section, Skeleton, SwitchRow } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { useShortcutScope } from "@/core/shortcuts/registry";
import { useAccHref } from "../lib/api-base";
import { inr } from "../lib/format";
import { useRBar } from "../shell/rbar-context";
import { useEmployee, useSaveEmployee, type Employee } from "./api";
import { emptyEmployee, employeeSchema, fromEmployee, monthlyGross, toEmployeeIn, type EmployeeForm, type EmployeeValues } from "./employee-schema";

function Components({ control, register, name, label }: { control: Control<EmployeeForm, unknown, EmployeeValues>; register: UseFormRegister<EmployeeForm>; name: "other_allowances" | "other_deductions"; label: string }) {
  const arr = useFieldArray({ control, name });
  return (
    <div className="flex flex-col gap-2">
      {arr.fields.map((f, i) => (
        <div key={f.id} className="grid grid-cols-[minmax(0,1fr)_160px_36px] gap-2">
          <Input aria-label={`${label} name`} placeholder="Name" {...register(`${name}.${i}.name`)} />
          <Input aria-label={`${label} amount`} inputMode="decimal" placeholder="₹ / month" {...register(`${name}.${i}.amount`)} />
          <Button size="icon" variant="ghost" aria-label="Remove" onClick={() => arr.remove(i)}><Trash2 /></Button>
        </div>
      ))}
      <Button size="sm" variant="ghost" className="self-start" onClick={() => arr.append({ name: "", amount: "" })}>+ Add {label.toLowerCase()}</Button>
    </div>
  );
}

function Editor({ initial, emp }: { initial: EmployeeForm; emp?: Employee }) {
  useShortcutScope("master");
  const router = useRouter();
  const href = useAccHref();
  const save = useSaveEmployee();
  const form = useZodForm(employeeSchema, { defaultValues: initial });
  const { register, control, watch, formState: { errors } } = form;
  const back = () => router.push(emp ? href(`/payroll/employees/${emp.id}`) : href("/payroll/employees"));
  const submit = form.handleSubmit(async (v) => {
    try {
      const out = await save.mutateAsync({ id: emp?.id, body: toEmployeeIn(v) });
      router.push(href(`/payroll/employees/${out.id}`));
    } catch (e) {
      applyServerErrors(form, e);
    }
  });
  useRBar([{ id: "accept", combo: "ctrl+a", label: "Accept", run: () => void submit() }, { id: "quit", combo: "escape", label: "Quit", run: back }], "master");
  const v = watch();
  const money = (k: "basic" | "da" | "hra" | "special" | "conveyance" | "piece_rate" | "monthly_tds_override", label: string, required?: boolean) => (
    <Field label={label} required={required} error={errors[k]?.message}><Input inputMode="decimal" {...register(k)} /></Field>
  );
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Employees", href: href("/payroll/employees") }, { label: emp?.full_name ?? "New employee" }]}
        title={emp ? "Alter employee" : "Create employee"} description="Employee master · salary structure · statutory applicability"
        actions={<><Button variant="ghost" onClick={back}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => void submit()}>Save employee</Button></>} />
      <Card>
        <form className="flex flex-col gap-5" onSubmit={submit} noValidate>
          <Section title="Employee">
            <div className="flex flex-col gap-3">
              <FieldRow>
                <Field label="Employee code" required error={errors.emp_code?.message}><Input autoFocus {...register("emp_code")} /></Field>
                <Field label="Full name" required error={errors.full_name?.message}><Input {...register("full_name")} /></Field>
              </FieldRow>
              <FieldRow>
                <Field label="Category" hint="Shop-floor wages are allocated to period runs"><NativeSelect {...register("employee_category")}><option value="SHOP_FLOOR_OPERATOR">Shop-floor operator</option><option value="STAFF">Staff</option><option value="MANAGEMENT">Management</option></NativeSelect></Field>
                <Field label="Date of joining" required error={errors.date_of_joining?.message}><Controller control={control} name="date_of_joining" render={({ field }) => <DatePicker value={field.value} onValueChange={(d) => field.onChange(d ?? "")} />} /></Field>
              </FieldRow>
              <FieldRow>
                <Field label="Department"><Input {...register("department")} /></Field>
                <Field label="Designation"><Input {...register("designation")} /></Field>
              </FieldRow>
            </div>
          </Section>
          <Section title="Statutory & bank">
            <div className="flex flex-col gap-3">
              <FieldRow>
                <Field label="PAN" error={errors.pan?.message}><Input className="uppercase" {...register("pan")} /></Field>
                <Field label="UAN (EPF)" error={errors.uan_epf?.message}><Input inputMode="numeric" {...register("uan_epf")} /></Field>
                <Field label="ESIC IP no." error={errors.esic_ip_no?.message}><Input inputMode="numeric" {...register("esic_ip_no")} /></Field>
              </FieldRow>
              <FieldRow>
                <Field label="Bank A/c no."><Input {...register("bank_account_no")} /></Field>
                <Field label="IFSC" error={errors.bank_ifsc?.message}><Input className="uppercase" {...register("bank_ifsc")} /></Field>
                <Field label="Tax regime"><NativeSelect {...register("tax_regime")}><option value="NEW">New regime</option><option value="OLD">Old regime</option></NativeSelect></Field>
              </FieldRow>
            </div>
          </Section>
          <Section title="Salary structure (monthly)" description={`Fixed gross ${inr(monthlyGross(v))} · EPF/ESIC/PT/TDS are computed on the pay run`}>
            <div className="flex flex-col gap-3">
              <FieldRow>{money("basic", "Basic", true)}{money("da", "DA")}{money("hra", "HRA")}</FieldRow>
              <FieldRow>{money("special", "Special allowance")}{money("conveyance", "Conveyance")}{money("piece_rate", "Piece rate (₹ / unit)")}</FieldRow>
              <p className="text-[12.5px] font-medium text-fg-2">Other allowances</p>
              <Components control={control} register={register} name="other_allowances" label="Allowance" />
              <p className="text-[12.5px] font-medium text-fg-2">Other deductions (loans, advances)</p>
              <Components control={control} register={register} name="other_deductions" label="Deduction" />
              <div className="grid gap-2 md:grid-cols-3">
                <Controller control={control} name="epf_applicable" render={({ field }) => <SwitchRow label="EPF" description="12% on min(Basic+DA, ₹15,000)" checked={field.value} onCheckedChange={field.onChange} />} />
                <Controller control={control} name="esic_applicable" render={({ field }) => <SwitchRow label="ESIC" description="When gross ≤ ₹21,000" checked={field.value} onCheckedChange={field.onChange} />} />
                <Controller control={control} name="pt_applicable" render={({ field }) => <SwitchRow label="Professional tax" description="State slab" checked={field.value} onCheckedChange={field.onChange} />} />
              </div>
              <FieldRow>{money("monthly_tds_override", "Monthly TDS override (Sec 192)")}</FieldRow>
            </div>
          </Section>
          <button type="submit" hidden />
        </form>
      </Card>
    </>
  );
}

/** /accounts/payroll/employees/new and /[id]/edit (design: Acc-Pay-Employee). */
export function EmployeeEditor({ id }: { id?: string }) {
  const q = useEmployee(id);
  if (!id) return <Editor initial={emptyEmployee()} />;
  if (q.isPending) return <Skeleton className="h-96 w-full" />;
  if (q.isError) return <ErrorState message={describeError(q.error)} onRetry={() => void q.refetch()} />;
  return <Editor key={q.data.id} initial={fromEmployee(q.data)} emp={q.data} />;
}
