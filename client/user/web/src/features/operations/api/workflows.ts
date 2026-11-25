"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { idempotencyHeader, unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { H } from "./params";
import { useOpsInvalidate, useOpsKey } from "./keys";

export function useWorkflowLibrary() {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({ queryKey: key("workflow-library"), queryFn: () => unwrap(api.GET("/api/v1/operations/workflow-library")), staleTime: 300_000 });
}

export function useWorkflows(query: { q?: string; stock_item_id?: string; all_versions?: boolean } = {}) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("workflows", query),
    queryFn: () => unwrap(api.GET("/api/v1/operations/workflows", { params: { query } })),
    placeholderData: (prev) => prev,
  });
}

export function useWorkflow(id: string) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("workflow", id),
    queryFn: () => unwrap(api.GET("/api/v1/operations/workflows/{workflow_id}", { params: { path: { workflow_id: id } } })),
    refetchOnWindowFocus: false,
  });
}

export function useWorkflowVersions(id: string, enabled = true) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("workflow", id, "versions"),
    queryFn: () => unwrap(api.GET("/api/v1/operations/workflows/{workflow_id}/versions", { params: { path: { workflow_id: id } } })),
    enabled,
  });
}

export function useCreateWorkflow() {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["WorkflowIn"]) => unwrap(api.POST("/api/v1/operations/workflows", { params: H, body, headers: idempotencyHeader() })),
    onSuccess: () => inv(),
    meta: { successMessage: "Workflow created" },
  });
}

/** Draft auto-save (silent: the editor shows its own "Saved / Couldn’t save" status). */
export function useSaveWorkflow(id: string) {
  const { api } = useOrg();
  return useMutation({
    mutationFn: (body: Schemas["WorkflowUpdateIn"]) =>
      unwrap(api.PUT("/api/v1/operations/workflows/{workflow_id}", { params: { ...H, path: { workflow_id: id } }, body })),
    meta: { silentError: true },
  });
}

export function useDeleteWorkflow() {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/operations/workflows/{workflow_id}", { params: { path: { workflow_id: id } } })),
    onSuccess: () => inv(),
    meta: { successMessage: "Workflow deleted" },
  });
}

export function useValidateWorkflow(id: string) {
  const { api } = useOrg();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/operations/workflows/{workflow_id}/validate", { params: { ...H, path: { workflow_id: id } } })),
  });
}

export function usePublishWorkflow(id: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/operations/workflows/{workflow_id}/publish", { params: { ...H, path: { workflow_id: id } } })),
    onSuccess: () => inv(),
    meta: { successMessage: "Workflow published" },
  });
}

export function useNewWorkflowVersion(id: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/operations/workflows/{workflow_id}/new-version", { params: { ...H, path: { workflow_id: id } } })),
    onSuccess: () => inv(),
    meta: { successMessage: "New draft version created" },
  });
}
