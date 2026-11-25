"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { useDocInvalidate, useDocKey } from "./keys";
import { H } from "./params";

export type TemplateOut = Schemas["TemplateOut"];
export const REPORT_DOC = "REPORT_DOC";
export const MONTHLY_FOLDER_RULE = "MONTHLY_FOLDER_RULE";

export function useTemplates(templateType?: string) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("templates", templateType ?? "all"),
    queryFn: () => unwrap(api.GET("/api/v1/documents/templates", { params: { query: templateType ? { template_type: templateType } : {} } })),
  });
}

export function useTemplate(id: string | null) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("template", id),
    queryFn: () => unwrap(api.GET("/api/v1/documents/templates/{template_id}", { params: { path: { template_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useTemplateTokens(enabled = true) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({ queryKey: key("template-tokens"), queryFn: () => unwrap(api.GET("/api/v1/documents/template-tokens")), staleTime: 600_000, enabled });
}

export function useCreateTemplate() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["TemplateIn"]) => unwrap(api.POST("/api/v1/documents/templates", { params: H, body })),
    onSuccess: () => inv("templates"),
    meta: { successMessage: "Template created" },
  });
}

export function useUpdateTemplate(id: string) {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["TemplateUpdateIn"]) =>
      unwrap(api.PATCH("/api/v1/documents/templates/{template_id}", { params: { path: { template_id: id } }, body })),
    onSuccess: () => inv(),
    meta: { successMessage: "Template saved" },
  });
}

export function useDeleteTemplate() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/documents/templates/{template_id}", { params: { path: { template_id: id } } })),
    onSuccess: () => inv("templates"),
    meta: { successMessage: "Template deleted" },
  });
}

export function useCloneTemplate() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.POST("/api/v1/documents/templates/{template_id}/clone", { params: { ...H, path: { template_id: id } } })),
    onSuccess: () => inv("templates"),
    meta: { successMessage: "Template copied — you can edit your copy" },
  });
}

export function usePreviewTemplate(id: string) {
  const { api } = useOrg();
  return useMutation({
    mutationFn: (context: Schemas["RenderContext"]) =>
      unwrap(api.POST("/api/v1/documents/templates/{template_id}/preview", { params: { ...H, path: { template_id: id } }, body: { context } })),
  });
}
