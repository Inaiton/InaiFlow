"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useAcc } from "../lib/api-base";
import { fetchFile } from "../lib/download";

export function useGstSummary(period: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("gst", "summary", period), queryFn: () => unwrap(api.GET("/api/v1/accounts/taxation/gst/summary", { params: { query: { period } } })), placeholderData: keepPreviousData });
}

export function useGstr1(period: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("gst", "gstr1", period), queryFn: () => unwrap(api.GET("/api/v1/accounts/taxation/gst/gstr1", { params: { query: { period } } })), placeholderData: keepPreviousData });
}

export function useGstr3b(period: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("gst", "gstr3b", period), queryFn: () => unwrap(api.GET("/api/v1/accounts/taxation/gst/gstr3b", { params: { query: { period } } })), placeholderData: keepPreviousData });
}

export function useGstValidate(period: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("gst", "validate", period), queryFn: () => unwrap(api.GET("/api/v1/accounts/taxation/gst/validate", { params: { query: { period } } })), placeholderData: keepPreviousData });
}

export function useGstExport() {
  const { api } = useAcc();
  return useMutation({
    mutationFn: ({ form, period }: { form: "gstr1" | "gstr3b"; period: string }) =>
      form === "gstr1"
        ? fetchFile(api.GET("/api/v1/accounts/taxation/gst/gstr1/export", { params: { query: { period } }, parseAs: "blob" }), `GSTR1_${period}.json`)
        : fetchFile(api.GET("/api/v1/accounts/taxation/gst/gstr3b/export", { params: { query: { period } }, parseAs: "blob" }), `GSTR3B_${period}.json`),
  });
}

export function useGstr2bRecon(period: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("gst", "gstr2b", period), queryFn: () => unwrap(api.GET("/api/v1/accounts/taxation/gst/gstr2b/reconciliation", { params: { query: { period } } })), placeholderData: keepPreviousData });
}

export function useImportGstr2b(period: string) {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (file: File) =>
      unwrap(api.POST("/api/v1/accounts/taxation/gst/gstr2b/import", {
        params: { query: { period } },
        body: { file: "" },
        bodySerializer: () => {
          const fd = new FormData();
          fd.append("file", file, file.name);
          return fd;
        },
      })),
    onSuccess: () => invalidate("gst"),
    meta: { successMessage: "GSTR-2B imported" },
  });
}

export function useEinvoice(voucherId: string, enabled = true) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("einvoice", voucherId),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/taxation/einvoice/{voucher_id}", { params: { path: { voucher_id: voucherId } } })),
    enabled,
  });
}

export function useEinvoiceAction(voucherId: string) {
  const { api, invalidate } = useAcc();
  const p = { params: { path: { voucher_id: voucherId } } };
  return useMutation({
    mutationFn: (a: { kind: "generate" } | { kind: "cancel"; body: Schemas["EinvoiceCancelIn"] } | { kind: "eway"; body: Schemas["EwayBillIn"] }) => {
      if (a.kind === "generate") return unwrap(api.POST("/api/v1/accounts/taxation/einvoice/{voucher_id}/generate", p));
      if (a.kind === "cancel") return unwrap(api.POST("/api/v1/accounts/taxation/einvoice/{voucher_id}/cancel", { ...p, body: a.body }));
      return unwrap(api.POST("/api/v1/accounts/taxation/ewaybill/{voucher_id}/generate", { ...p, body: a.body }));
    },
    onSuccess: () => invalidate("einvoice", voucherId),
    meta: { successMessage: "Updated with the IRP (mock gateway)" },
  });
}

export function useTdsSections(onDate?: string) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("tds", "sections", onDate),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/taxation/tds/sections", { params: { query: onDate ? { on_date: onDate } : {} } })),
    staleTime: 5 * 60_000,
  });
}

export function useTdsCompute() {
  const { api } = useAcc();
  return useMutation({ mutationFn: (body: Schemas["TdsComputeIn"]) => unwrap(api.POST("/api/v1/accounts/taxation/tds/compute", { body })) });
}

export function useTdsSummary(from: string, to: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("tds", "summary", from, to), queryFn: () => unwrap(api.GET("/api/v1/accounts/taxation/tds/summary", { params: { query: { date_from: from, date_to: to } } })), placeholderData: keepPreviousData });
}

export function useTdsChallan(month: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("tds", "challan", month), queryFn: () => unwrap(api.GET("/api/v1/accounts/taxation/tds/challan", { params: { query: { month } } })), placeholderData: keepPreviousData });
}

export function useTdsReturn() {
  const { api } = useAcc();
  return useMutation({
    mutationFn: ({ form, quarter }: { form: string; quarter: string }) =>
      fetchFile(api.GET("/api/v1/accounts/taxation/tds/returns/{form}", { params: { path: { form }, query: { quarter } }, parseAs: "blob" }), `${form}_${quarter}.txt`),
  });
}
