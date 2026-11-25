"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import type { ApiPaths, Schemas } from "@/core/api/types";
import { useAcc } from "../lib/api-base";

export type LedgerQuery = NonNullable<ApiPaths["/api/v1/accounts/ledgers"]["get"]["parameters"]["query"]>;
export type Ledger = Schemas["LedgerOut"];
export type Group = Schemas["GroupOut"];

/* ---------- groups ---------- */
export function useGroups() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("groups"), queryFn: () => unwrap(api.GET("/api/v1/accounts/groups")), staleTime: 60_000 });
}

export function useSaveGroup() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["GroupIn"] | Schemas["GroupUpdateIn"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/accounts/groups/{group_id}", { params: { path: { group_id: id } }, body }))
        : unwrap(api.POST("/api/v1/accounts/groups", { body: body as Schemas["GroupIn"] })),
    onSuccess: () => invalidate("groups"),
    meta: { successMessage: "Group saved" },
  });
}

export function useDeleteGroup() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/accounts/groups/{group_id}", { params: { path: { group_id: id } } })),
    onSuccess: () => invalidate("groups"),
    meta: { successMessage: "Group deleted" },
  });
}

/* ---------- ledgers ---------- */
export function useLedgers(query: LedgerQuery, enabled = true) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("ledgers", "list", query),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/ledgers", { params: { query } })),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useLedger(id: string | null | undefined) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("ledgers", "one", id),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/ledgers/{ledger_id}", { params: { path: { ledger_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useSaveLedger() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["LedgerIn"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/accounts/ledgers/{ledger_id}", { params: { path: { ledger_id: id } }, body }))
        : unwrap(api.POST("/api/v1/accounts/ledgers", { body })),
    onSuccess: () => invalidate("ledgers"),
    meta: { successMessage: "Ledger saved" },
  });
}

export function useDeleteLedger() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/accounts/ledgers/{ledger_id}", { params: { path: { ledger_id: id } } })),
    onSuccess: () => invalidate("ledgers"),
    meta: { successMessage: "Ledger deleted" },
  });
}

export function useLedgerStatement(id: string, from: string, to: string) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("ledgers", "statement", id, from, to),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/ledgers/{ledger_id}/statement", { params: { path: { ledger_id: id }, query: { date_from: from, date_to: to } } })),
    placeholderData: keepPreviousData,
  });
}

export function useOutstandingBills(id: string | null | undefined, asOf?: string) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("ledgers", "bills", id, asOf),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/ledgers/{ledger_id}/bills", { params: { path: { ledger_id: id! }, query: asOf ? { as_of: asOf } : {} } })),
    enabled: Boolean(id),
  });
}

/* ---------- cost centres ---------- */
export function useCostCentres(enabled = true) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("cost-centres"), queryFn: () => unwrap(api.GET("/api/v1/accounts/cost-centres")), enabled, staleTime: 30_000 });
}

export function useSaveCostCentre() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["CostCentreIn"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/accounts/cost-centres/{cost_centre_id}", { params: { path: { cost_centre_id: id } }, body }))
        : unwrap(api.POST("/api/v1/accounts/cost-centres", { body })),
    onSuccess: () => invalidate("cost-centres"),
    meta: { successMessage: "Cost centre saved" },
  });
}

export function useDeleteCostCentre() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/accounts/cost-centres/{cost_centre_id}", { params: { path: { cost_centre_id: id } } })),
    onSuccess: () => invalidate("cost-centres"),
    meta: { successMessage: "Cost centre deleted" },
  });
}

/* ---------- voucher types ---------- */
export function useVoucherTypes() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("voucher-types"), queryFn: () => unwrap(api.GET("/api/v1/accounts/voucher-types")), staleTime: 60_000 });
}

export function useSaveVoucherType() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["VoucherTypeIn"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/accounts/voucher-types/{voucher_type_id}", { params: { path: { voucher_type_id: id } }, body }))
        : unwrap(api.POST("/api/v1/accounts/voucher-types", { body })),
    onSuccess: () => invalidate("voucher-types"),
    meta: { successMessage: "Voucher type saved" },
  });
}

/* ---------- currencies ---------- */
export function useCurrencies() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("currencies"), queryFn: () => unwrap(api.GET("/api/v1/accounts/currencies")) });
}

export function useCreateCurrency() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (body: Schemas["CurrencyIn"]) => unwrap(api.POST("/api/v1/accounts/currencies", { body })),
    onSuccess: () => invalidate("currencies"),
    meta: { successMessage: "Currency added" },
  });
}

export function useAddRate() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["ExchangeRateIn"] }) =>
      unwrap(api.POST("/api/v1/accounts/currencies/{currency_id}/rates", { params: { path: { currency_id: id } }, body })),
    onSuccess: () => invalidate("currencies"),
    meta: { successMessage: "Exchange rate saved" },
  });
}

/* ---------- settings ---------- */
export function useAccountsSettings() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("settings"), queryFn: () => unwrap(api.GET("/api/v1/accounts/settings")), staleTime: 60_000 });
}

export function useSaveAccountsSettings() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (body: Schemas["AccountsSettings"]) => unwrap(api.PUT("/api/v1/accounts/settings", { body })),
    onSuccess: () => invalidate("settings"),
    meta: { successMessage: "Accounts settings saved" },
  });
}

/* ---------- meta ---------- */
export function useStates() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("meta-states"), queryFn: () => unwrap(api.GET("/api/v1/meta/states")), staleTime: Infinity });
}
