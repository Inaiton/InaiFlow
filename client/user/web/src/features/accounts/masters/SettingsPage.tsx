"use client";

import { useState } from "react";
import { Button, Card, DatePicker, Field, FieldRow, NativeSelect, PageHeader, Section, SwitchRow, Textarea } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { useCan } from "@/core/permissions/Can";
import { QueryState } from "../components/QueryState";
import { useAccHref } from "../lib/api-base";
import { useAccountsSettings, useSaveAccountsSettings, useVoucherTypes } from "./api";

function Form({ initial }: { initial: Schemas["AccountsSettings"] }) {
  const save = useSaveAccountsSettings();
  const types = useVoucherTypes();
  const canFull = useCan("accounts.vouchers", "FULL");
  const [s, setS] = useState(initial);
  const text = (k: "invoice_terms" | "invoice_declaration" | "invoice_bank_details" | "invoice_footer", label: string) => (
    <Field label={label}><Textarea rows={3} disabled={!canFull} value={s[k] ?? ""} onChange={(e) => setS({ ...s, [k]: e.target.value || null })} /></Field>
  );
  const vtSelect = (k: "default_sales_voucher_type_id" | "default_purchase_voucher_type_id", base: string, label: string) => (
    <Field label={label}><NativeSelect disabled={!canFull} value={s[k] ?? ""} onChange={(e) => setS({ ...s, [k]: e.target.value || null })}>
      <option value="">System default</option>{(types.data ?? []).filter((t) => t.base_type === base).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
    </NativeSelect></Field>
  );
  return (
    <Card>
      <div className="flex flex-col gap-5">
        <Section title="Books" description="No voucher can be created, altered or cancelled on or before this date">
          <FieldRow><Field label="Books locked until"><DatePicker disabled={!canFull} value={s.books_locked_until} onValueChange={(v) => setS({ ...s, books_locked_until: v })} /></Field></FieldRow>
        </Section>
        <Section title="Invoice & print">
          <div className="flex flex-col gap-3">
            <SwitchRow label="Print the company logo" description="Logo from Organization → Profile" checked={s.invoice_show_logo} disabled={!canFull} onCheckedChange={(v) => setS({ ...s, invoice_show_logo: v })} />
            {text("invoice_bank_details", "Bank details")}{text("invoice_terms", "Terms & conditions")}{text("invoice_declaration", "Declaration")}{text("invoice_footer", "Footer")}
          </div>
        </Section>
        <Section title="Default voucher types"><FieldRow>{vtSelect("default_sales_voucher_type_id", "SALES", "Sales")}{vtSelect("default_purchase_voucher_type_id", "PURCHASE", "Purchase")}</FieldRow></Section>
        {canFull ? <Button variant="primary" className="self-end" loading={save.isPending} onClick={() => save.mutate(s)}>Save settings</Button> : null}
      </div>
    </Card>
  );
}

/** /accounts/settings — period lock and invoice layout (design: Acc-Settings-Invoice). */
export function AccountsSettingsPage() {
  const href = useAccHref();
  const q = useAccountsSettings();
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Settings" }]} title="Accounts settings" description="F12 configure · applies to every voucher and printed bill" />
      <QueryState q={q}>{(s) => <Form initial={s} />}</QueryState>
    </>
  );
}
