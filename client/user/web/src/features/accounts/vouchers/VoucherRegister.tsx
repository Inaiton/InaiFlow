"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, Card, DatePicker, ErrorState, Field, Input, NativeSelect, PageHeader } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { sum } from "@/core/money";
import { Can } from "@/core/permissions/Can";
import { Amt } from "../components/Amount";
import { LedgerPicker } from "../components/LedgerPicker";
import { VoucherTable } from "../gateway/RecentVouchers";
import { useAccHref } from "../lib/api-base";
import { useDebouncedValue } from "../lib/hooks";
import { humanize } from "../lib/format";
import { usePeriod } from "../lib/use-period";
import { ORDER_BASES, VOUCHER_KINDS } from "../lib/voucher-kinds";
import { useRBar } from "../shell/rbar-context";
import { voucherKeys } from "../shell/default-rbar";
import { useVouchers, type VoucherQuery } from "./api";

const PAGE = 50;

/** /accounts/vouchers (register) and /accounts/vouchers/orders (orders only). */
export function VoucherRegister({ orders }: { orders?: boolean }) {
  const href = useAccHref();
  const { period, setPeriod } = usePeriod();
  const [base, setBase] = useState(orders ? "SALES_ORDER" : "");
  const [status, setStatus] = useState("");
  const [party, setParty] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(text, 300);
  const query: VoucherQuery = {
    date_from: period.from, date_to: period.to, limit: PAGE, offset,
    ...(base ? { base_type: base } : {}), ...(status ? { status: status as VoucherQuery["status"] } : {}), ...(party ? { party_ledger_id: party } : {}), ...(q ? { q } : {}),
  };
  const list = useVouchers(query);
  useRBar(voucherKeys(href), "accounts");
  const kinds = VOUCHER_KINDS.filter((k) => (orders ? ORDER_BASES.includes(k.base) : true));
  const reset = () => { setOffset(0); };
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: orders ? "Orders" : "Vouchers" }]}
        title={orders ? "Orders & notes" : "Voucher register"}
        description={orders ? "Sales/purchase orders, delivery & receipt notes, job work — not posted to books" : "Every voucher with filters · click a row to open the bill"}
        actions={<Can permission="accounts.vouchers" level="WRITE"><Button asChild variant="primary"><Link href={href(`/vouchers/new?type=${orders ? base || "SALES_ORDER" : "SALES"}`)}>{orders ? `New ${humanize(base || "SALES_ORDER").toLowerCase()}` : "New sales (F8)"}</Link></Button></Can>} />
      <Card padded={false}>
        <div className="grid grid-cols-2 gap-3 border-b border-line p-4 md:grid-cols-6">
          <Field label="From"><DatePicker value={period.from} onValueChange={(v) => { if (v) { reset(); setPeriod({ ...period, from: v }); } }} /></Field>
          <Field label="To"><DatePicker value={period.to} onValueChange={(v) => { if (v) { reset(); setPeriod({ ...period, to: v }); } }} /></Field>
          <Field label="Voucher type"><NativeSelect value={base} onChange={(e) => { reset(); setBase(e.target.value); }}>
            {orders ? null : <option value="">All types</option>}{kinds.map((k) => <option key={k.base} value={k.base}>{k.label}</option>)}
          </NativeSelect></Field>
          <Field label="Status"><NativeSelect value={status} onChange={(e) => { reset(); setStatus(e.target.value); }}>
            <option value="">All</option>{["REGULAR", "OPTIONAL", "MEMORANDUM", "POST_DATED", "CANCELLED"].map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
          </NativeSelect></Field>
          <Field label="Party"><div className="rounded-lg border border-line"><LedgerPicker value={party} filter={{ party_only: true }} placeholder="All parties" onChange={(l) => { reset(); setParty(l.id); }} /></div></Field>
          <Field label="Search"><Input value={text} onChange={(e) => { reset(); setText(e.target.value); }} placeholder="No., narration, ref…" /></Field>
        </div>
        {party || status || base || q ? <div className="px-4 pt-2"><Button size="sm" variant="ghost" onClick={() => { setParty(null); setStatus(""); setBase(orders ? "SALES_ORDER" : ""); setText(""); reset(); }}>Clear filters</Button></div> : null}
        {list.isError ? <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} /> : (
          <VoucherTable data={list.data?.items} loading={list.isPending}
            pagination={list.data ? { total: list.data.total, limit: list.data.limit, offset: list.data.offset, onOffsetChange: setOffset } : undefined} />
        )}
        {list.data ? (
          <div className="flex justify-end gap-6 border-t border-line px-4 py-2.5 text-[13px]">
            <span className="text-fg-muted">{list.data.total} vouchers</span>
            <span>Page total <Amt strong v={sum(list.data.items.filter((v) => v.status !== "CANCELLED").map((v) => v.total_amount))} /></span>
          </div>
        ) : null}
      </Card>
    </>
  );
}
