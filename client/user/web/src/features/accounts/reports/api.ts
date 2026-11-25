"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import { useAcc } from "../lib/api-base";
import { fetchFile } from "../lib/download";

type Range = { date_from: string; date_to: string };

export function useDashboard() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("dashboard"), queryFn: () => unwrap(api.GET("/api/v1/accounts/dashboard")) });
}

export function useTrialBalance(q: Range & { mode?: string }) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("reports", "trial-balance", q), queryFn: () => unwrap(api.GET("/api/v1/accounts/reports/trial-balance", { params: { query: q } })), placeholderData: keepPreviousData });
}

export function useProfitLoss(q: Range) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("reports", "profit-loss", q), queryFn: () => unwrap(api.GET("/api/v1/accounts/reports/profit-loss", { params: { query: q } })), placeholderData: keepPreviousData });
}

export function useBalanceSheet(asOf: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("reports", "balance-sheet", asOf), queryFn: () => unwrap(api.GET("/api/v1/accounts/reports/balance-sheet", { params: { query: { as_of: asOf } } })), placeholderData: keepPreviousData });
}

export function useCashFlow(q: Range) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("reports", "cash-flow", q), queryFn: () => unwrap(api.GET("/api/v1/accounts/reports/cash-flow", { params: { query: q } })), placeholderData: keepPreviousData });
}

export function useRatios(q: Range) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("reports", "ratios", q), queryFn: () => unwrap(api.GET("/api/v1/accounts/reports/ratios", { params: { query: q } })), placeholderData: keepPreviousData });
}

export function useAgeing(q: { kind: string; as_of: string; buckets?: string }) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("reports", "ageing", q), queryFn: () => unwrap(api.GET("/api/v1/accounts/reports/ageing", { params: { query: q } })), placeholderData: keepPreviousData });
}

export function useBatchCosting(q: Range) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("reports", "batch-costing", q), queryFn: () => unwrap(api.GET("/api/v1/accounts/reports/batch-costing", { params: { query: q } })), placeholderData: keepPreviousData });
}

export type ExportQuery = { format: "csv" | "pdf"; date_from?: string; date_to?: string; as_of?: string; kind?: string };

export function useReportExport() {
  const { api } = useAcc();
  return useMutation({
    mutationFn: ({ report, query }: { report: string; query: ExportQuery }) =>
      fetchFile(api.GET("/api/v1/accounts/reports/{report}/export", { params: { path: { report }, query }, parseAs: "blob" }), `${report}.${query.format}`, query.format === "pdf" ? "open" : "save"),
  });
}

export function useExceptions() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("utilities", "exceptions"), queryFn: () => unwrap(api.GET("/api/v1/accounts/utilities/exceptions")) });
}

export function useTallyExport() {
  const { api } = useAcc();
  return useMutation({
    mutationFn: (q: Range) => fetchFile(api.GET("/api/v1/accounts/utilities/tally-export", { params: { query: q }, parseAs: "blob" }), `tally-export_${q.date_from}_${q.date_to}.xml`),
    meta: { successMessage: "Tally XML downloaded" },
  });
}

export function useAccountsAuditLog(q: { limit: number; offset: number; date_from?: string; date_to?: string }, enabled: boolean) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("utilities", "audit", q),
    queryFn: () => unwrap(api.GET("/api/v1/organization/audit-logs", { params: { query: { module: "ACCOUNTS", ...q } } })),
    enabled,
    placeholderData: keepPreviousData,
  });
}
