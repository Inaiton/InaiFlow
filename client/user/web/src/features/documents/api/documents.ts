"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { idempotencyHeader, unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { putWithProgress } from "../lib/transfer";
import { useDocInvalidate, useDocKey } from "./keys";
import { H } from "./params";

export type DocumentSummary = Schemas["DocumentSummary"];
export type DocumentOut = Schemas["DocumentOut"];
export type ApprovalStatus = Schemas["ApprovalStatus"];
export type DocsQuery = {
  folder_id?: string; q?: string; source_type?: string; approval_status?: ApprovalStatus; linked_period_run_id?: string;
  linked_step_id?: string; linked_voucher_id?: string; linked_stock_item_id?: string; iso_only?: boolean; limit: number; offset: number;
};

export function useDocuments(query: DocsQuery, enabled = true) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("list", query),
    queryFn: () => unwrap(api.GET("/api/v1/documents", { params: { query } })),
    placeholderData: (prev) => prev,
    enabled,
  });
}

export function useDocument(id: string | null) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("doc", id),
    queryFn: () => unwrap(api.GET("/api/v1/documents/{document_id}", { params: { path: { document_id: id! } } })),
    enabled: Boolean(id),
    refetchOnWindowFocus: false,
  });
}

export function useDocSearch(q: string) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("search", q),
    queryFn: () => unwrap(api.GET("/api/v1/documents/search", { params: { query: { q, limit: 30 } } })),
    enabled: q.trim().length >= 2,
    placeholderData: (prev) => prev,
  });
}

export type UploadMeta = Omit<Schemas["DocUploadIn"], "file_name" | "content_type" | "size_bytes">;

/** upload-url → raw PUT (progress) → complete-upload. Returns the ready document. */
export function useUploadDocument() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: async ({ file, meta, onProgress }: { file: File | Blob; meta: UploadMeta; onProgress?: (p: number) => void }) => {
      const name = file instanceof File ? file.name : `${meta.title}.pdf`;
      const body: Schemas["DocUploadIn"] = { ...meta, file_name: name, content_type: file.type || "application/octet-stream", size_bytes: file.size };
      const out = await unwrap(api.POST("/api/v1/documents/upload-url", { params: H, body, headers: idempotencyHeader() }));
      await putWithProgress(out.upload, file, onProgress);
      return unwrap(api.POST("/api/v1/documents/{document_id}/complete-upload", { params: { ...H, path: { document_id: out.document.id } }, body: {} }));
    },
    onSuccess: () => inv(),
    meta: { silentError: true },
  });
}

export function useCreateDocument() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["DocCreateIn"]) => unwrap(api.POST("/api/v1/documents", { params: H, body, headers: idempotencyHeader() })),
    onSuccess: () => inv(),
  });
}

export function useUpdateDocument(id: string, opts: { silent?: boolean } = {}) {
  const { api } = useOrg();
  const qc = useQueryClient();
  const key = useDocKey();
  return useMutation({
    mutationFn: (body: Schemas["DocUpdateIn"]) => unwrap(api.PATCH("/api/v1/documents/{document_id}", { params: { path: { document_id: id } }, body })),
    onSuccess: (doc) => {
      qc.setQueryData(key("doc", id), doc);
      void qc.invalidateQueries({ queryKey: key("list") });
    },
    meta: opts.silent ? { silentError: true } : { successMessage: "Saved" },
  });
}

export function useDeleteDocument() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/documents/{document_id}", { params: { path: { document_id: id } } })),
    onSuccess: () => inv(),
    meta: { successMessage: "Document deleted" },
  });
}

/** Signed URL (≤5 min) issued after RBAC — fetched on demand, never cached long. */
export function useDownloadUrl(id: string | null, enabled = true) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("doc", id, "url"),
    queryFn: () => unwrap(api.GET("/api/v1/documents/{document_id}/download-url", { params: { path: { document_id: id! } } })),
    enabled: Boolean(id) && enabled,
    staleTime: 120_000,
    gcTime: 180_000,
  });
}

export function useExportDocument(id: string) {
  const { api } = useOrg();
  return useMutation({
    mutationFn: (format: "pdf" | "docx") =>
      unwrap(api.GET("/api/v1/documents/{document_id}/export", { params: { path: { document_id: id }, query: { format } }, parseAs: "blob" })),
  });
}

export function useTransition(id: string) {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["TransitionIn"]) => unwrap(api.POST("/api/v1/documents/{document_id}/transition", { params: { ...H, path: { document_id: id } }, body })),
    onSuccess: () => inv(),
    meta: { silentError: true },
  });
}

export function useReview(id: string) {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["ReviewIn"]) => unwrap(api.POST("/api/v1/documents/{document_id}/review", { params: { ...H, path: { document_id: id } }, body })),
    onSuccess: () => inv(),
    meta: { silentError: true },
  });
}

/** New revision; for file documents the new file is uploaded to the returned ticket. */
export function useRevise(id: string) {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: async (file?: File) => {
      const body: Schemas["ReviseIn"] = file ? { file: { file_name: file.name, content_type: file.type || "application/octet-stream", size_bytes: file.size } } : {};
      const out = await unwrap(api.POST("/api/v1/documents/{document_id}/revise", { params: { ...H, path: { document_id: id } }, body }));
      if (file && out.upload) {
        await putWithProgress(out.upload, file);
        return unwrap(api.POST("/api/v1/documents/{document_id}/complete-upload", { params: { ...H, path: { document_id: out.document.id } }, body: {} }));
      }
      return out.document;
    },
    onSuccess: () => inv(),
    meta: { successMessage: "New revision created" },
  });
}

export function useVersions(id: string | null) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("doc", id, "versions"),
    queryFn: () => unwrap(api.GET("/api/v1/documents/{document_id}/versions", { params: { path: { document_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useDocAudit(id: string | null, enabled = true) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("doc", id, "audit"),
    queryFn: () => unwrap(api.GET("/api/v1/documents/{document_id}/audit", { params: { path: { document_id: id! } } })),
    enabled: Boolean(id) && enabled,
  });
}
