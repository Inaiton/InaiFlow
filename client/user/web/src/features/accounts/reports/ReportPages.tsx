"use client";

import { ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Card, Hint, Segmented } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { isNegative, isZero, neg } from "@/core/money";
import { cn } from "@/lib/utils";
import { Amt } from "../components/Amount";
import { QueryState } from "../components/QueryState";
import { useAccHref } from "../lib/api-base";
import { amt } from "../lib/format";
import { periodQuery, usePeriod } from "../lib/use-period";
import { useBalanceSheet, useCashFlow, useProfitLoss, useRatios, useTrialBalance } from "./api";
import { ReportFrame } from "./ReportFrame";
import { StatementTree, TotalLine } from "./StatementTree";

type TbRow = Schemas["TrialBalanceRow"];

/** /accounts/reports/trial-balance — grouped (expand/collapse) or ledger-wise (design: Acc-Rep-Trial). */
export function TrialBalancePage() {
  const p = usePeriod();
  const href = useAccHref();
  const router = useRouter();
  const [mode, setMode] = useState<"grouped" | "ledger">("grouped");
  const [open, setOpen] = useState<Set<string>>(new Set());
  const range = { date_from: p.period.from, date_to: p.period.to };
  const q = useTrialBalance({ ...range, mode });
  const visible = (r: TbRow, byId: Map<string, TbRow>) => { let pid = r.parent_id; while (pid) { if (!open.has(pid)) return false; pid = byId.get(pid)?.parent_id ?? null; } return true; };
  return (
    <ReportFrame title="Trial balance" report="trial-balance" {...p} exportQuery={range} extraKeys={[{ id: "mode", combo: "f5", label: mode === "grouped" ? "Ledger-wise" : "Group-wise", run: () => setMode((m) => (m === "grouped" ? "ledger" : "grouped")) }]}
      actions={<Segmented value={mode} onChange={setMode} options={[{ value: "grouped", label: "Group-wise" }, { value: "ledger", label: "Ledger-wise" }]} />}>
      <Card padded={false}>
        <QueryState q={q} rows={10}>
          {(tb) => {
            const byId = new Map(tb.rows.map((r) => [r.id, r]));
            const hasKids = new Set(tb.rows.map((r) => r.parent_id).filter(Boolean) as string[]);
            return (
              <>
                {!isZero(tb.difference) ? <Hint tone="danger" title="Difference in trial balance">{amt(tb.difference)} — check the exceptions report.</Hint> : null}
                <table className="w-full text-[13px]">
                  <thead><tr className="border-b border-line bg-subtle text-[11.5px] text-fg-muted"><th className="px-3 py-2 text-left font-semibold">Particulars</th>{["Opening Dr", "Opening Cr", "Debit", "Credit", "Closing Dr", "Closing Cr"].map((h) => <th key={h} className="px-3 text-right font-semibold">{h}</th>)}</tr></thead>
                  <tbody>{tb.rows.filter((r) => mode === "ledger" || visible(r, byId)).map((r) => {
                    const group = r.kind === "GROUP";
                    return (
                      <tr key={r.id} className={cn("border-b border-line/60 hover:bg-subtle", group ? "font-semibold text-ink" : "cursor-pointer")}
                        onClick={() => (group ? setOpen((s) => { const n = new Set(s); if (n.has(r.id)) n.delete(r.id); else n.add(r.id); return n; }) : router.push(href(`/masters/ledgers/${r.id}?${periodQuery(p.period)}`)))}>
                        <td className="py-1.5 pr-3" style={{ paddingLeft: 12 + (mode === "ledger" ? 0 : r.level * 18) }}>
                          <span className="flex items-center gap-1">{group && hasKids.has(r.id) ? <ChevronRight className={cn("size-3.5 text-fg-muted transition-transform", open.has(r.id) && "rotate-90")} aria-hidden /> : null}{r.name}</span>
                        </td>
                        {(["opening_dr", "opening_cr", "debit", "credit", "closing_dr", "closing_cr"] as const).map((k) => <td key={k} className="px-3 text-right"><Amt v={r[k]} blankZero /></td>)}
                      </tr>
                    );
                  })}</tbody>
                  <tfoot><tr className="border-t-2 border-fg font-semibold text-ink"><td className="px-3 py-2">Grand total</td><td colSpan={2} /><td className="px-3 text-right"><Amt v={tb.total_debit} /></td><td className="px-3 text-right"><Amt v={tb.total_credit} /></td><td colSpan={2} className="px-3 text-right">{isZero(tb.difference) ? <Badge tone="success">Balanced</Badge> : null}</td></tr></tfoot>
                </table>
              </>
            );
          }}
        </QueryState>
      </Card>
    </ReportFrame>
  );
}

/** /accounts/reports/profit-loss — Tally T-format: trading account then P&L, two columns (design: Acc-Rep-PL). */
export function ProfitLossPage() {
  const p = usePeriod();
  const range = { date_from: p.period.from, date_to: p.period.to };
  const q = useProfitLoss(range);
  const pq = periodQuery(p.period);
  return (
    <ReportFrame title="Profit & loss A/c" report="profit-loss" {...p} exportQuery={range}>
      <QueryState q={q} rows={10}>
        {(pl) => {
          const gp = !isNegative(pl.gross_profit);
          const np = !isNegative(pl.net_profit);
          return (
            <div className="grid gap-0 overflow-hidden rounded-xl border border-line bg-surface md:grid-cols-2">
              <div className="border-line md:border-r">
                <h2 className="bg-subtle px-3 py-2 text-[12px] font-semibold text-fg-2">Particulars (Dr)</h2>
                <TotalLine label="Opening stock" v={pl.opening_stock} />
                <StatementTree sections={pl.trading_debit} q={pq} />
                {gp ? <TotalLine label="Gross profit c/o" v={pl.gross_profit} strong /> : null}
                <StatementTree sections={pl.pnl_debit} q={pq} />
                {!gp ? <TotalLine label="Gross loss b/f" v={neg(pl.gross_profit)} /> : null}
                {np ? <TotalLine label="Net profit" v={pl.net_profit} strong /> : null}
              </div>
              <div>
                <h2 className="bg-subtle px-3 py-2 text-[12px] font-semibold text-fg-2">Particulars (Cr)</h2>
                <StatementTree sections={pl.trading_credit} q={pq} />
                <TotalLine label="Closing stock" v={pl.closing_stock} />
                {!gp ? <TotalLine label="Gross loss c/o" v={neg(pl.gross_profit)} strong /> : null}
                {gp ? <TotalLine label="Gross profit b/f" v={pl.gross_profit} /> : null}
                <StatementTree sections={pl.pnl_credit} q={pq} />
                {!np ? <TotalLine label="Net loss" v={neg(pl.net_profit)} strong /> : null}
              </div>
            </div>
          );
        }}
      </QueryState>
    </ReportFrame>
  );
}

/** /accounts/reports/balance-sheet — Schedule-III vertical format. */
export function BalanceSheetPage() {
  const p = usePeriod();
  const q = useBalanceSheet(p.period.to);
  return (
    <ReportFrame title="Balance sheet" report="balance-sheet" {...p} asOf exportQuery={{ as_of: p.period.to }}>
      <QueryState q={q} rows={10}>
        {(bs) => (
          <Card padded={false}>
            {!isZero(bs.difference) ? <Hint tone="danger" title="Balance sheet doesn’t tally">Difference {amt(bs.difference)} — usually opening balances or a suspense entry.</Hint> : null}
            <h2 className="bg-subtle px-3 py-2 text-[12px] font-semibold text-fg-2">I. Equity and liabilities</h2>
            <StatementTree sections={bs.equity_and_liabilities} q={periodQuery(p.period)} />
            <TotalLine label="Total equity and liabilities" v={bs.total_liabilities} strong />
            <h2 className="bg-subtle px-3 py-2 text-[12px] font-semibold text-fg-2">II. Assets</h2>
            <StatementTree sections={bs.assets} q={periodQuery(p.period)} />
            <TotalLine label="Total assets" v={bs.total_assets} strong />
          </Card>
        )}
      </QueryState>
    </ReportFrame>
  );
}

/** /accounts/reports/cash-flow (design: Acc-Rep-CashFlow). */
export function CashFlowPage() {
  const p = usePeriod();
  const range = { date_from: p.period.from, date_to: p.period.to };
  const q = useCashFlow(range);
  return (
    <ReportFrame title="Cash flow" report="cash-flow" {...p} exportQuery={range}>
      <QueryState q={q}>
        {(cf) => (
          <Card padded={false}>
            <TotalLine label="Opening cash & bank" v={cf.opening_cash} />
            {([["A. Operating activities", cf.operating], ["B. Investing activities", cf.investing], ["C. Financing activities", cf.financing]] as const).map(([l, s]) => (
              <div key={l}><h2 className="bg-subtle px-3 py-2 text-[12px] font-semibold text-fg-2">{l}</h2><StatementTree sections={[...s]} /></div>
            ))}
            <TotalLine label="Net change in cash" v={cf.net_change} />
            <TotalLine label="Closing cash & bank" v={cf.closing_cash} strong />
          </Card>
        )}
      </QueryState>
    </ReportFrame>
  );
}

/** /accounts/reports/ratios */
export function RatiosPage() {
  const p = usePeriod();
  const range = { date_from: p.period.from, date_to: p.period.to };
  const q = useRatios(range);
  return (
    <ReportFrame title="Ratio analysis" report="ratios" {...p} exportQuery={range}>
      <QueryState q={q}>
        {(rows) => (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {rows.map((r) => <Card key={r.key}><p className="text-[12.5px] text-fg-muted">{r.label}</p><p className="text-[22px] font-semibold text-ink tabular">{r.value ?? "—"}</p><p className="text-[11.5px] text-fg-muted">{r.formula}</p></Card>)}
          </div>
        )}
      </QueryState>
    </ReportFrame>
  );
}
