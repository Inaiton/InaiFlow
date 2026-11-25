"use client";

/* eslint-disable @next/next/no-img-element -- org logo is a signed storage URL */
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { useCan } from "@/core/permissions/Can";
import { Amt } from "../../components/Amount";
import { amountInWords } from "../../lib/amount-words";
import { accDate, inr, qty } from "../../lib/format";
import { INVOICE_BASES, kindOf } from "../../lib/voucher-kinds";
import { useAccountsSettings, useLedger } from "../../masters/api";
import { useLetterhead, type Voucher } from "../api";

const TITLES: Record<string, string> = { SALES: "TAX INVOICE", PURCHASE: "PURCHASE VOUCHER", CREDIT_NOTE: "CREDIT NOTE", DEBIT_NOTE: "DEBIT NOTE" };

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="flex flex-col gap-0.5 border-b border-line px-3 py-1.5 last:border-b-0"><span className="text-[10.5px] font-semibold tracking-wide text-fg-muted uppercase">{label}</span><span className="text-[13px] font-medium text-ink">{value}</span></div>;
}

/** Printable bill (design: Acc-V-Sales / Acc-V-Saved): letterhead + logo, GSTIN, items, tax lines, amount in words, signatures. */
export function BillDocument({ v, settings }: { v: Voucher; settings?: Schemas["AccountsSettings"] }) {
  const { context } = useOrg();
  const canProfile = useCan("organization.profile", "READ");
  const head = useLetterhead(canProfile);
  const s = useAccountsSettings();
  const cfg = settings ?? s.data;
  const party = useLedger(v.party_ledger_id);
  const kind = kindOf(v.base_type);
  const invoice = INVOICE_BASES.includes(v.base_type) || Boolean(kind?.order);
  const p = head.data;
  const pd = party.data?.party_details;
  const showLogo = (cfg?.invoice_show_logo ?? true) && (p?.logo_url ?? context.logo_url);
  const extraEntries = v.entries.filter((e) => e.ledger_id !== v.party_ledger_id);
  const cancelled = v.status === "CANCELLED";
  return (
    <article className="relative flex flex-col overflow-hidden rounded-xl border border-line bg-surface text-[13px]" aria-label={`${v.voucher_type_name} ${v.voucher_number}`}>
      {cancelled ? <div className="pointer-events-none absolute inset-0 grid place-items-center"><span className="-rotate-12 rounded-xl border-4 border-danger px-6 py-2 text-4xl font-bold text-danger/60">CANCELLED</span></div> : null}
      <header className="flex flex-wrap items-start gap-4 border-b border-line p-4">
        {showLogo ? <img src={(p?.logo_url ?? context.logo_url)!} alt="" className="h-14 w-auto max-w-[140px] object-contain" /> : null}
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <h2 className="text-[17px] font-semibold text-ink">{p?.legal_name ?? context.legal_name}</h2>
          {p ? <p className="text-[12px] text-fg-3">{[p.address_line1, p.address_line2, p.city, `${p.state_name} ${p.pincode}`].filter(Boolean).join(", ")}</p> : null}
          {p ? <p className="text-[12px] text-fg-3">{p.gstin ? `GSTIN ${p.gstin} · ` : ""}{p.pan ? `PAN ${p.pan} · ` : ""}State code {p.state_code}{p.contact_phone ? ` · ${p.contact_phone}` : ""}{p.contact_email ? ` · ${p.contact_email}` : ""}</p> : null}
        </div>
        <div className="text-right">
          <p className="text-[15px] font-bold tracking-wide text-ink">{TITLES[v.base_type] ?? v.voucher_type_name.toUpperCase()}</p>
          {v.base_type === "SALES" ? <p className="text-[11.5px] text-fg-muted">Original for recipient</p> : null}
        </div>
      </header>
      <div className="grid border-b border-line md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="border-line p-3 md:border-r">
          {v.party_name ? (
            <>
              <p className="text-[10.5px] font-semibold tracking-wide text-fg-muted uppercase">{v.base_type === "PURCHASE" || v.base_type === "DEBIT_NOTE" ? "Supplier (bill from)" : "Buyer (bill to)"}</p>
              <p className="font-semibold text-ink">{v.party_name}</p>
              {pd?.address ? <p className="text-[12px] text-fg-3">{pd.address}</p> : null}
              <p className="text-[12px] text-fg-3">{pd?.gstin ? `GSTIN ${pd.gstin}` : "Unregistered"}{pd?.state_code ? ` · State code ${pd.state_code}` : ""}</p>
            </>
          ) : <p className="text-fg-muted">{v.voucher_type_name}</p>}
        </div>
        <div className="grid grid-cols-2">
          <Meta label="Voucher no." value={v.voucher_number} />
          <Meta label="Dated" value={accDate(v.voucher_date)} />
          {v.supplier_invoice_no ? <Meta label={v.base_type === "SALES" ? "Buyer’s order no." : "Supplier invoice no."} value={v.supplier_invoice_no} /> : null}
          {v.supplier_invoice_date ? <Meta label="Invoice date" value={accDate(v.supplier_invoice_date)} /> : null}
          {v.status !== "REGULAR" ? <Meta label="Status" value={v.status.replace("_", " ")} /> : null}
        </div>
      </div>
      {invoice && v.inventory.length ? (
        <table className="w-full">
          <thead><tr className="border-b border-line bg-subtle text-[11px] tracking-wide text-fg-muted uppercase">
            <th className="px-3 py-1.5 text-left font-semibold">#</th><th className="text-left font-semibold">Name of item</th><th className="text-right font-semibold">Quantity</th>
            <th className="text-right font-semibold">Rate</th><th className="text-left font-semibold pl-2">Per</th><th className="text-right font-semibold">GST</th><th className="px-3 text-right font-semibold">Amount</th>
          </tr></thead>
          <tbody>{v.inventory.map((i, n) => (
            <tr key={i.id} className="border-b border-line/60 align-top">
              <td className="px-3 py-1.5 text-fg-muted">{n + 1}</td>
              <td className="py-1.5"><span className="font-medium text-ink">{i.stock_item_name}</span><span className="block text-[11.5px] text-fg-muted">Godown: {i.godown_name}{i.batch_number ? ` · Batch ${i.batch_number}` : ""}</span></td>
              <td className="text-right tabular">{qty(i.quantity)} {i.uom}</td><td className="text-right"><Amt v={i.rate} /></td><td className="pl-2 text-fg-muted">{i.uom}</td>
              <td className="text-right text-fg-muted">{i.gst_rate ? `${Number(i.gst_rate)}%` : "—"}</td><td className="px-3 text-right"><Amt v={i.amount} /></td>
            </tr>
          ))}</tbody>
        </table>
      ) : null}
      <table className="w-full">
        {!invoice ? <thead><tr className="border-b border-line bg-subtle text-[11px] tracking-wide text-fg-muted uppercase"><th className="px-3 py-1.5 text-left font-semibold">Dr/Cr</th><th className="text-left font-semibold">Particulars</th><th className="text-right font-semibold">Debit</th><th className="px-3 text-right font-semibold">Credit</th></tr></thead> : null}
        <tbody>{(invoice ? extraEntries : v.entries).map((e) => (
          <tr key={e.id} className="border-b border-line/60 align-top">
            {invoice ? <td className="w-8" /> : <td className="px-3 py-1.5 font-semibold text-fg-3">{e.entry_type === "DR" ? "Dr" : "Cr"}</td>}
            <td className="py-1.5">
              <span className={invoice ? "text-fg-3" : "font-medium text-ink"}>{e.ledger_name}</span>
              {e.cost_centre_name ? <span className="block text-[11.5px] text-fg-muted">Cost centre: {e.cost_centre_name}</span> : null}
              {e.bill_allocations.length ? <span className="block text-[11.5px] text-fg-muted">{e.bill_allocations.map((b) => `${b.ref_type.replace("_", " ").toLowerCase()} ${b.ref_name}`).join(" · ")}</span> : null}
              {e.instrument_no ? <span className="block text-[11.5px] text-fg-muted">Inst. {e.instrument_no}{e.instrument_date ? ` · ${accDate(e.instrument_date)}` : ""}{e.bank_reconciliation_date ? ` · reconciled ${accDate(e.bank_reconciliation_date)}` : ""}</span> : null}
            </td>
            {invoice ? <td className="px-3 text-right" colSpan={2}><Amt v={e.amount} /></td> : <><td className="text-right">{e.entry_type === "DR" ? <Amt v={e.amount} /> : null}</td><td className="px-3 text-right">{e.entry_type === "CR" ? <Amt v={e.amount} /> : null}</td></>}
          </tr>
        ))}</tbody>
      </table>
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line px-3 py-2.5">
        <p className="max-w-xl text-[12px] text-fg-3"><span className="text-fg-muted">Amount chargeable (in words): </span>{amountInWords(v.total_amount)}</p>
        <p className="text-[16px] font-semibold text-ink">Total {inr(v.total_amount)}</p>
      </div>
      {v.narration ? <p className="border-b border-line px-3 py-2 text-[12.5px]"><span className="text-fg-muted">Narration: </span>{v.narration}</p> : null}
      {invoice && (cfg?.invoice_bank_details || cfg?.invoice_terms || cfg?.invoice_declaration) ? (
        <div className="grid gap-3 border-b border-line p-3 text-[12px] md:grid-cols-2">
          {cfg?.invoice_bank_details ? <div><p className="font-semibold text-fg-2">Bank details</p><p className="whitespace-pre-line text-fg-3">{cfg.invoice_bank_details}</p></div> : null}
          {cfg?.invoice_terms ? <div><p className="font-semibold text-fg-2">Terms</p><p className="whitespace-pre-line text-fg-3">{cfg.invoice_terms}</p></div> : null}
          {cfg?.invoice_declaration ? <div className="md:col-span-2"><p className="font-semibold text-fg-2">Declaration</p><p className="text-fg-3">{cfg.invoice_declaration}</p></div> : null}
        </div>
      ) : null}
      <footer className="grid grid-cols-2 gap-4 p-3 text-[12px] text-fg-3">
        <div className="flex flex-col justify-end gap-1">
          {v.base_type === "SALES" ? <p className="border-t border-dashed border-line-strong pt-1">Customer’s seal and signature</p> : null}
          <p>Prepared by {v.created_by_name}{v.approved_by_name ? ` · Approved by ${v.approved_by_name}` : ""}</p>
        </div>
        <div className="flex flex-col items-end justify-end gap-6 text-right">
          <p>for <span className="font-semibold text-ink">{p?.legal_name ?? context.legal_name}</span></p>
          <p className="border-t border-line-strong pt-1">Authorised signatory</p>
        </div>
      </footer>
      {cfg?.invoice_footer ? <p className="border-t border-line px-3 py-1.5 text-center text-[11.5px] text-fg-muted">{cfg.invoice_footer}</p> : null}
    </article>
  );
}
