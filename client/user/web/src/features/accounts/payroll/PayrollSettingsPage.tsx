"use client";

import { useState } from "react";
import { Button, Card, Field, FieldRow, NativeSelect, PageHeader } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { useCan } from "@/core/permissions/Can";
import { LedgerPicker } from "../components/LedgerPicker";
import { QueryState } from "../components/QueryState";
import { StateSelect } from "../components/Selects";
import { PAYROLL_NAV, SubNav } from "../components/SubNav";
import { useAccHref } from "../lib/api-base";
import { usePayrollSettings, useSavePayrollSettings } from "./api";

type S = Schemas["PayrollSettingsOut"];
const LEDGERS: [keyof S, string][] = [
  ["salary_payable_ledger_id", "Salary payable"], ["direct_wages_ledger_id", "Direct wages (production)"], ["admin_salary_ledger_id", "Admin salaries"],
  ["employer_contrib_ledger_id", "Employer PF & ESIC"], ["epf_payable_ledger_id", "EPF payable"], ["esic_payable_ledger_id", "ESIC payable"],
  ["pt_payable_ledger_id", "PT payable"], ["tds_payable_ledger_id", "TDS on salary payable"], ["default_bank_ledger_id", "Default salary bank"],
];

function Form({ initial }: { initial: S }) {
  const save = useSavePayrollSettings();
  const canFull = useCan("accounts.payroll_runs", "FULL");
  const [s, setS] = useState(initial);
  return (
    <Card>
      <div className="flex flex-col gap-4">
        <FieldRow>
          <Field label="Professional tax state"><StateSelect value={s.pt_state_code ?? ""} onValueChange={(v) => setS({ ...s, pt_state_code: v || null })} placeholder="No PT" /></Field>
          <Field label="Working days basis"><NativeSelect value={s.working_days_basis} onChange={(e) => setS({ ...s, working_days_basis: e.target.value })}><option value="CALENDAR">Calendar days</option><option value="FIXED_26">Fixed 26 days</option><option value="FIXED_30">Fixed 30 days</option></NativeSelect></Field>
        </FieldRow>
        <div className="grid gap-3 md:grid-cols-3">
          {LEDGERS.map(([k, label]) => (
            <Field key={k} label={label}><div className="rounded-lg border border-line"><LedgerPicker value={s[k] as string | null} filter={k === "default_bank_ledger_id" ? { bank_only: true } : undefined} onChange={(l) => setS({ ...s, [k]: l.id })} /></div></Field>
          ))}
        </div>
        {canFull ? <Button variant="primary" className="self-end" loading={save.isPending} onClick={() => save.mutate(s)}>Save settings</Button> : null}
      </div>
    </Card>
  );
}

/** /accounts/payroll/settings — PT state and ledger mapping for payroll postings. */
export function PayrollSettingsPage() {
  const href = useAccHref();
  const q = usePayrollSettings();
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Payroll", href: href("/payroll") }, { label: "Settings" }]} title="Payroll settings" description="Where the payroll voucher posts" />
      <SubNav items={PAYROLL_NAV} />
      <QueryState q={q}>{(s) => <Form initial={s} />}</QueryState>
    </>
  );
}
