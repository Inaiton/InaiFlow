"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useAcc } from "../lib/api-base";
import { fetchFile } from "../lib/download";

export function useBankAccounts() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("banking", "accounts"), queryFn: () => unwrap(api.GET("/api/v1/accounts/banking/accounts")) });
}

export function useReconciliation(ledgerId: string, asOf: string, show: string) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("banking", "recon", ledgerId, asOf, show),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/banking/{ledger_id}/reconciliation", { params: { path: { ledger_id: ledgerId }, query: { as_of: asOf, show } } })),
    placeholderData: keepPreviousData,
  });
}

export function useSetReconDate() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ entryId, date }: { entryId: string; date: string | null }) =>
      unwrap(api.PATCH("/api/v1/accounts/banking/entries/{entry_id}/reconcile", { params: { path: { entry_id: entryId } }, body: { bank_reconciliation_date: date } })),
    onSuccess: () => invalidate("banking"),
  });
}

export function useImportStatement(ledgerId: string) {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (file: File) =>
      unwrap(api.POST("/api/v1/accounts/banking/{ledger_id}/statements/import", {
        params: { path: { ledger_id: ledgerId } },
        // openapi types the multipart field as string (binary); send the real File via FormData
        body: { file: "" },
        bodySerializer: () => {
          const fd = new FormData();
          fd.append("file", file, file.name);
          return fd;
        },
      })),
    onSuccess: () => invalidate("banking"),
    meta: { successMessage: "Statement imported" },
  });
}

export function useStatementLines(ledgerId: string, status: string | undefined, offset: number) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("banking", "lines", ledgerId, status, offset),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/banking/{ledger_id}/statement-lines", { params: { path: { ledger_id: ledgerId }, query: { ...(status ? { status } : {}), limit: 50, offset } } })),
    placeholderData: keepPreviousData,
  });
}

export function useLineAction() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ lineId, action, entryId }: { lineId: string; action: "match" | "unmatch" | "ignore"; entryId?: string }) => {
      const p = { params: { path: { line_id: lineId } } };
      if (action === "match") return unwrap(api.POST("/api/v1/accounts/banking/statement-lines/{line_id}/match", { ...p, body: { entry_id: entryId! } }));
      if (action === "unmatch") return unwrap(api.POST("/api/v1/accounts/banking/statement-lines/{line_id}/unmatch", p));
      return unwrap(api.POST("/api/v1/accounts/banking/statement-lines/{line_id}/ignore", p));
    },
    onSuccess: () => invalidate("banking"),
  });
}

export function useChequeBooks(bankLedgerId?: string) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("banking", "cheque-books", bankLedgerId),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/banking/cheque-books", { params: { query: bankLedgerId ? { bank_ledger_id: bankLedgerId } : {} } })),
  });
}

export function useCreateChequeBook() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (body: Schemas["ChequeBookIn"]) => unwrap(api.POST("/api/v1/accounts/banking/cheque-books", { body })),
    onSuccess: () => invalidate("banking"),
    meta: { successMessage: "Cheque book added" },
  });
}

export function useCheques(query: { bank_ledger_id?: string; date_from?: string; date_to?: string }) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("banking", "cheques", query),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/banking/cheques", { params: { query } })),
    placeholderData: keepPreviousData,
  });
}

export function usePrintCheque() {
  const { api } = useAcc();
  return useMutation({
    mutationFn: (entryId: string) =>
      fetchFile(api.GET("/api/v1/accounts/banking/cheques/{entry_id}/print", { params: { path: { entry_id: entryId } }, parseAs: "blob" }), "cheque.pdf", "open"),
  });
}
