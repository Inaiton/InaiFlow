"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { idempotencyHeader, unwrap } from "@/core/api/client";
import type { ApiPaths, Schemas } from "@/core/api/types";
import { useAcc } from "../lib/api-base";
import { fetchFile } from "../lib/download";

export type VoucherQuery = NonNullable<ApiPaths["/api/v1/accounts/vouchers"]["get"]["parameters"]["query"]>;
export type Voucher = Schemas["VoucherOut"];
export type VoucherSummary = Schemas["VoucherSummary"];

export function useVouchers(query: VoucherQuery) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("vouchers", "list", query),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/vouchers", { params: { query } })),
    placeholderData: keepPreviousData,
  });
}

export function useVoucher(id: string | null | undefined) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("vouchers", "one", id),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/vouchers/{voucher_id}", { params: { path: { voucher_id: id! } } })),
    enabled: Boolean(id),
  });
}

function useInvalidateBooks() {
  const { invalidate } = useAcc();
  // vouchers move balances everywhere: ledgers, reports, stock, dashboard
  return () => invalidate();
}

/** Create (no id) or edit (id + body.edit_reason). The caller owns the Idempotency-Key (one per submission). */
export function useSaveVoucher() {
  const { api } = useAcc();
  const inv = useInvalidateBooks();
  return useMutation({
    mutationFn: ({ id, body, key }: { id?: string; body: Schemas["VoucherIn"]; key: string }) =>
      id
        ? unwrap(api.PUT("/api/v1/accounts/vouchers/{voucher_id}", { params: { path: { voucher_id: id }, header: idempotencyHeader(key) }, body }))
        : unwrap(api.POST("/api/v1/accounts/vouchers", { params: { header: idempotencyHeader(key) }, body })),
    onSuccess: () => void inv(),
    meta: { silentError: true },
  });
}

export function useCancelVoucher() {
  const { api } = useAcc();
  const inv = useInvalidateBooks();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      unwrap(api.POST("/api/v1/accounts/vouchers/{voucher_id}/cancel", { params: { path: { voucher_id: id } }, body: { reason } })),
    onSuccess: () => void inv(),
    meta: { successMessage: "Voucher cancelled" },
  });
}

export function useComputeTax(body: Schemas["ComputeTaxIn"] | null) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("compute-tax", body),
    queryFn: () => unwrap(api.POST("/api/v1/accounts/vouchers/compute-tax", { body: body! })),
    enabled: body !== null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    retry: false,
  });
}

export function useEditLog(id: string, enabled = true) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("vouchers", "edit-log", id),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/vouchers/{voucher_id}/edit-log", { params: { path: { voucher_id: id } } })),
    enabled,
  });
}

export function useAttachDocument() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, documentId }: { id: string; documentId: string }) =>
      unwrap(api.POST("/api/v1/accounts/vouchers/{voucher_id}/attachments", { params: { path: { voucher_id: id } }, body: { document_id: documentId } })),
    onSuccess: () => invalidate("vouchers"),
  });
}

export function usePrintVoucher() {
  const { api } = useAcc();
  return useMutation({
    mutationFn: ({ id, number }: { id: string; number: string }) =>
      fetchFile(api.GET("/api/v1/accounts/vouchers/{voucher_id}/print", { params: { path: { voucher_id: id }, query: { format: "pdf" } }, parseAs: "blob" }), `${number.replace(/[\\/]/g, "-")}.pdf`, "open"),
  });
}

export function useDayBook(query: { date_from: string; date_to: string; limit: number; offset: number }) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("reports", "day-book", query),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/reports/day-book", { params: { query } })),
    placeholderData: keepPreviousData,
  });
}

/** Company letterhead for printable vouchers (only when the user may read the org profile). */
export function useLetterhead(enabled: boolean) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("letterhead"), queryFn: () => unwrap(api.GET("/api/v1/organization/profile")), enabled, staleTime: 5 * 60_000, retry: false });
}
