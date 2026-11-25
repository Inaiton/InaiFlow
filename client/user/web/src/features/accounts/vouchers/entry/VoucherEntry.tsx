"use client";

import { useRouter } from "next/navigation";
import { useMemo, useReducer, useRef, useState } from "react";
import { ConfirmDialog, PageHeader } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { todayIso } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { useShortcutScope } from "@/core/shortcuts/registry";
import { QuickItemDialog } from "../../components/QuickItemDialog";
import { QuickLedgerDialog } from "../../components/QuickLedgerDialog";
import { useInventoryDefaults } from "../../inventory/defaults";
import { useAccHref } from "../../lib/api-base";
import { handleEnterAdvance } from "../../lib/enter-nav";
import { useDebouncedValue } from "../../lib/hooks";
import type { VoucherKind } from "../../lib/voucher-kinds";
import { useRBar } from "../../shell/rbar-context";
import { voucherKeys } from "../../shell/default-rbar";
import { useComputeTax, type Voucher } from "../api";
import type { Schemas } from "@/core/api/types";
import { AccountingGrid } from "./AccountingGrid";
import { defaultPartyBills, toComputeTaxIn, toVoucherIn, validateDraft } from "./build";
import { draftReducer, emptyDraft } from "./draft";
import { draftFromVoucher } from "./from-voucher";
import { InventoryLines } from "./InventoryLines";
import { InvoiceHeader } from "./InvoiceHeader";
import { InvoiceItems } from "./InvoiceItems";
import { TaxSummary } from "./TaxSummary";
import { TdsHelper } from "./TdsHelper";
import { VoucherFooter } from "./VoucherFooter";
import { VoucherHead, expectedNumber } from "./VoucherHead";
import { useVoucherSave } from "./useVoucherSave";

type Create = { kind: "ledger" | "item"; name: string; target: { row?: string; field?: "party" | "ledger"; inv?: boolean } } | null;

/** Bill-style, keyboard-first voucher entry for every base type (design: Acc-Voucher, Acc-V-*). */
export function VoucherEntry({ kind, types, voucher }: { kind: VoucherKind; types: Schemas["VoucherTypeOut"][]; voucher?: Voucher }) {
  useShortcutScope("voucher");
  const router = useRouter();
  const href = useAccHref();
  const { context } = useOrg();
  const inv = useInventoryDefaults(kind);
  const [draft, dispatch] = useReducer(draftReducer, null, () =>
    voucher ? draftFromVoucher(voucher, kind) : emptyDraft(kind.base, types[0]?.id ?? "", todayIso(), inv.godownId));
  const [file, setFile] = useState<File | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const [create, setCreate] = useState<Create>(null);
  const [quit, setQuit] = useState(false);
  const [askReason, setAskReason] = useState(false);
  const formRef = useRef<HTMLDivElement>(null);
  const dateRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const { submit, saving, serverError } = useVoucherSave(voucher?.id);

  const taxIn = useMemo(() => (kind.mode === "invoice" && !kind.order ? toComputeTaxIn(draft) : null), [draft, kind]);
  const taxBody = useDebouncedValue(taxIn, 350);
  const tax = useComputeTax(taxBody);
  const taxData = taxIn ? tax.data : undefined;
  const errors = [...validateDraft(draft, kind, taxData), ...(serverError ? [serverError] : [])];
  const vt = types.find((t) => t.id === draft.voucher_type_id);
  const partyDue = useRef<number | null>(null);

  const accept = (reason?: string) => {
    setShowErrors(true);
    if (validateDraft(draft, kind, taxData).length) return;
    if (voucher && reason === undefined) return setAskReason(true);
    const body = toVoucherIn(draft, { kind, tax: taxData, editReason: reason, partyBills: (amt) => defaultPartyBills(draft, amt, expectedNumber(vt), partyDue.current) });
    void submit(body, file, "view");
  };
  const close = () => router.push(voucher ? href(`/vouchers/${voucher.id}`) : href("/daybook"));
  const requestQuit = () => (draft.acc.some((r) => r.ledger_id) || draft.items.some((r) => r.stock_item_id) || draft.party_ledger_id ? setQuit(true) : close());

  useRBar([
    { id: "date", combo: "f2", label: "Date", run: () => dateRef.current?.focus() },
    ...voucherKeys(href, kind.base).map((i, n) => ({ ...i, sep: n === 0, disabled: Boolean(voucher) })),
    { id: "create", combo: "alt+c", label: "Create master", sep: true, run: () => setCreate({ kind: kind.mode === "accounting" ? "ledger" : "item", name: "", target: {} }) },
    { id: "attach", combo: "alt+v", label: "Attach bill", run: () => fileRef.current?.click(), disabled: kind.mode === "inventory" },
    { id: "accept", combo: "ctrl+a", label: "Accept", run: () => accept() },
    { id: "quit", combo: "escape", label: "Quit", run: requestQuit },
    { id: "configure", combo: "f12", label: "Configure", href: href("/settings") },
  ], "voucher");

  const onCreated = (id: string, l?: { maintain_bill_by_bill: boolean }) => {
    const t = create?.target ?? {};
    if (create?.kind === "ledger") {
      if (t.field === "party") dispatch({ type: "set", patch: { party_ledger_id: id, party_bill_wise: Boolean(l?.maintain_bill_by_bill) } });
      else if (t.field === "ledger") dispatch({ type: "set", patch: { ledger_id: id } });
      else if (t.row && kind.mode === "accounting") dispatch({ type: "acc", key: t.row, patch: { ledger_id: id, bill_wise: Boolean(l?.maintain_bill_by_bill) } });
      else if (t.row) dispatch({ type: "item", key: t.row, patch: { ledger_id: id } });
    } else if (t.row) {
      dispatch(t.inv ? { type: "inv", key: t.row, patch: { stock_item_id: id } } : { type: "item", key: t.row, patch: { stock_item_id: id, godown_id: inv.godownId } });
    }
    setCreate(null);
  };

  const tdsAmountBase = taxData?.invoice_total ?? "0";
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Vouchers", href: href("/vouchers") }, { label: kind.label }]}
        title={`${kind.label} voucher`} description={`${kind.combo ? kind.combo.toUpperCase().replace("+", " ") + " · " : ""}${kind.title}`} />
      <article aria-label="Voucher" className="rounded-xl border border-line bg-surface shadow-[0_8px_24px_rgba(16,24,40,0.06)]"
        ref={formRef} onKeyDown={(e) => handleEnterAdvance(e, formRef.current)}>
        <VoucherHead ref={dateRef} kind={kind} types={types} draft={draft} dispatch={dispatch} orgName={context.mailing_name || context.legal_name} number={voucher?.voucher_number} onClose={requestQuit} editing={Boolean(voucher)} />
        {kind.mode === "accounting" ? (
          <AccountingGrid draft={draft} dispatch={dispatch} kind={kind} onCreateLedger={(name, row) => setCreate({ kind: "ledger", name, target: { row } })} />
        ) : kind.mode === "invoice" ? (
          <>
            <InvoiceHeader draft={draft} dispatch={dispatch} kind={kind} onCreateLedger={(name, field) => setCreate({ kind: "ledger", name, target: { field } })} />
            <InvoiceItems draft={draft} dispatch={dispatch} defaultGodown={inv.godownId} onCreateItem={(name, row) => setCreate({ kind: "item", name, target: { row } })} onCreateLedger={(name, row) => setCreate({ kind: "ledger", name, target: { row } })} />
            {kind.tds && !kind.order ? <div className="border-t border-line"><TdsHelper partyLedgerId={draft.party_ledger_id} amount={tdsAmountBase} date={draft.date} applied={draft.tds} apply={(t) => dispatch({ type: "set", patch: { tds: t } })} /></div> : null}
            {kind.order ? null : <div className="border-t border-line"><TaxSummary tax={taxData} loading={tax.isFetching} error={tax.isError && taxIn ? describeError(tax.error) : undefined} input={kind.ledgerKind === "purchase"} tds={draft.tds?.amount} /></div>}
          </>
        ) : (
          <InventoryLines draft={draft} dispatch={dispatch} base={kind.base} defaultGodown={inv.godownId} onCreateItem={(name, row) => setCreate({ kind: "item", name, target: { row, inv: true } })} />
        )}
        <VoucherFooter ref={fileRef} narration={draft.narration} onNarration={(v) => dispatch({ type: "set", patch: { narration: v } })} file={file} onFile={setFile}
          errors={errors} showErrors={showErrors || Boolean(serverError)} saving={saving} onAccept={() => accept()} onQuit={requestQuit} canAttach={kind.mode !== "inventory"} />
      </article>
      <QuickLedgerDialog open={create?.kind === "ledger"} name={create?.name ?? ""} groupCode={create?.target.field === "party" ? (kind.partySide === "DR" ? "SUNDRY_DEBTORS" : "SUNDRY_CREDITORS") : create?.target.field === "ledger" ? (kind.ledgerKind === "sales" ? "SALES_ACCOUNTS" : "PURCHASE_ACCOUNTS") : undefined}
        onClose={() => setCreate(null)} onCreated={(l) => { if (create?.target.field === "party") partyDue.current = l.default_credit_days; onCreated(l.id, l); }} />
      <QuickItemDialog open={create?.kind === "item"} name={create?.name ?? ""} onClose={() => setCreate(null)} onCreated={(i) => onCreated(i.id)} />
      <ConfirmDialog open={quit} onOpenChange={setQuit} title="Quit without saving?" description="This voucher hasn’t been accepted. Your entries will be lost." confirmLabel="Quit" destructive onConfirm={close} />
      <ConfirmDialog open={askReason} onOpenChange={setAskReason} title="Reason for alteration" description="Edits keep the voucher number; the before/after is written to the edit log (MCA audit trail)."
        requireReason reasonLabel="Edit reason" confirmLabel="Save alteration" onConfirm={(r) => { setAskReason(false); accept(r); }} />
    </>
  );
}
