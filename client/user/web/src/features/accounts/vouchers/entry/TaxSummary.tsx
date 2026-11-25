"use client";

import { AlertTriangle } from "lucide-react";
import type { Schemas } from "@/core/api/types";
import { isZero } from "@/core/money";
import { Spinner } from "@/components/ui";
import { Amt } from "../../components/Amount";
import { amountInWords } from "../../lib/amount-words";
import { inr } from "../../lib/format";

type Tax = Schemas["ComputeTaxOut"];

/** Invoice tax breakup (CGST/SGST or IGST, round-off, total, HSN table, amount in words) from compute-tax. */
export function TaxSummary({ tax, loading, error, input, tds }: { tax: Tax | undefined; loading: boolean; error?: string; input: boolean; tds?: string }) {
  if (error) return <p className="flex items-center gap-2 px-3 py-2 text-[12.5px] text-danger-text"><AlertTriangle className="size-4" aria-hidden />{error}</p>;
  if (!tax) return <p className="flex items-center gap-2 px-3 py-3 text-[12.5px] text-fg-muted">{loading ? <><Spinner /> Calculating GST…</> : "Choose the party, ledger and at least one priced line to calculate GST."}</p>;
  const rows: [string, string][] = [["Taxable value", tax.taxable_total]];
  const pre = input ? "Input " : "";
  if (!isZero(tax.igst)) rows.push([`${pre}IGST`, tax.igst]);
  if (!isZero(tax.cgst)) rows.push([`${pre}CGST`, tax.cgst]);
  if (!isZero(tax.sgst)) rows.push([`${pre}SGST`, tax.sgst]);
  if (!isZero(tax.cess)) rows.push(["Cess", tax.cess]);
  if (!isZero(tax.round_off)) rows.push(["Round off", tax.round_off]);
  if (tds && !isZero(tds)) rows.push(["Less: TDS", `-${tds}`]);
  const igst = !isZero(tax.igst);
  return (
    <div className="grid gap-4 p-3 md:grid-cols-[minmax(0,1fr)_300px]">
      <div className="flex min-w-0 flex-col gap-2">
        <table className="w-full text-[12px]">
          <thead className="text-fg-muted"><tr className="border-b border-line">
            <th className="py-1 text-left font-medium">HSN/SAC</th><th className="text-right font-medium">Rate</th><th className="text-right font-medium">Taxable</th>
            {igst ? <th className="text-right font-medium">IGST</th> : <><th className="text-right font-medium">CGST</th><th className="text-right font-medium">SGST</th></>}
          </tr></thead>
          <tbody>{tax.breakup.map((b, i) => (
            <tr key={i} className="border-b border-line/60">
              <td className="py-1">{b.hsn_sac_code ?? "—"}</td><td className="text-right">{b.gst_rate}%</td><td className="text-right"><Amt v={b.taxable} /></td>
              {igst ? <td className="text-right"><Amt v={b.igst} /></td> : <><td className="text-right"><Amt v={b.cgst} /></td><td className="text-right"><Amt v={b.sgst} /></td></>}
            </tr>
          ))}</tbody>
        </table>
        <p className="text-[12px] text-fg-3"><span className="text-fg-muted">Amount chargeable (in words): </span>{amountInWords(tax.invoice_total)}</p>
        {tax.warnings.map((w) => <p key={w} className="flex items-center gap-1.5 text-[12px] text-warning-text"><AlertTriangle className="size-3.5" aria-hidden />{w}</p>)}
        <p className="text-[11.5px] text-fg-muted">Tax split: {tax.tax_split.replace(/_/g, " ")}{loading ? " · updating…" : ""}</p>
      </div>
      <dl className="flex flex-col gap-1 rounded-lg bg-subtle p-3 text-[13px]">
        {rows.map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-fg-3">{k}</dt><dd><Amt v={v} /></dd></div>)}
        <div className="mt-1 flex justify-between border-t border-line-strong pt-2 text-[15px] font-semibold text-ink"><dt>Invoice total</dt><dd className="tabular">{inr(tax.invoice_total)}</dd></div>
      </dl>
    </div>
  );
}
