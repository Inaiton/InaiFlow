"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { idempotencyHeader, unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { H } from "./params";
import { useOpsInvalidate, useOpsKey } from "./keys";

export type RunStatus = Schemas["RunStatus"];
export type RunsQuery = { status?: RunStatus; stock_item_id?: string; period_month?: string; q?: string; limit: number; offset: number };

export function useRuns(query: RunsQuery) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("runs", query),
    queryFn: () => unwrap(api.GET("/api/v1/operations/runs", { params: { query } })),
    placeholderData: (prev) => prev,
  });
}

export function useRun(runId: string) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("run", runId),
    queryFn: () => unwrap(api.GET("/api/v1/operations/runs/{run_id}", { params: { path: { run_id: runId } } })),
  });
}

export function useCreateRun() {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: ({ body, key }: { body: Schemas["RunCreateIn"]; key: string }) =>
      unwrap(api.POST("/api/v1/operations/runs", { params: H, body, headers: idempotencyHeader(key) })),
    onSuccess: () => inv({ accounts: true, documents: true }),
    meta: { successMessage: "Run launched" },
  });
}

type RunAction = "start" | "resume" | "complete";
type RunReasonAction = "hold" | "cancel";

/** Write the fresh RunOut into the cache, then refresh lists. */
function useRunCache(runId: string) {
  const qc = useQueryClient();
  const key = useOpsKey();
  const inv = useOpsInvalidate();
  return (run?: Schemas["RunOut"]) => {
    if (run) qc.setQueryData(key("run", runId), run);
    inv({ accounts: true });
  };
}

export function useRunAction(runId: string, action: RunAction) {
  const { api } = useOrg();
  const done = useRunCache(runId);
  const path = { run_id: runId };
  return useMutation({
    mutationFn: () => {
      if (action === "start") return unwrap(api.POST("/api/v1/operations/runs/{run_id}/start", { params: { ...H, path } }));
      if (action === "resume") return unwrap(api.POST("/api/v1/operations/runs/{run_id}/resume", { params: { ...H, path } }));
      return unwrap(api.POST("/api/v1/operations/runs/{run_id}/complete", { params: { ...H, path } }));
    },
    onSuccess: done,
    meta: { successMessage: action === "complete" ? "Run closed — costing posted" : action === "start" ? "Run started" : "Run resumed" },
  });
}

export function useRunReasonAction(runId: string, action: RunReasonAction) {
  const { api } = useOrg();
  const done = useRunCache(runId);
  const path = { run_id: runId };
  return useMutation({
    mutationFn: (reason: string) =>
      action === "hold"
        ? unwrap(api.POST("/api/v1/operations/runs/{run_id}/hold", { params: { ...H, path }, body: { reason } }))
        : unwrap(api.POST("/api/v1/operations/runs/{run_id}/cancel", { params: { ...H, path }, body: { reason } })),
    onSuccess: done,
    meta: { successMessage: action === "hold" ? "Run put on QC hold" : "Run cancelled" },
  });
}

type StepVars<B> = { stepId: string; body: B; key: string };

export function useExecuteStep(runId: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: ({ stepId, body, key }: StepVars<Schemas["StepExecuteIn"]>) =>
      unwrap(api.POST("/api/v1/operations/runs/{run_id}/steps/{step_id}/execute", {
        params: { ...H, path: { run_id: runId, step_id: stepId } }, body, headers: idempotencyHeader(key),
      })),
    onSuccess: () => inv({ accounts: true }),
    meta: { silentError: true },
  });
}

export function useSkipStep(runId: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: ({ stepId, body, key }: StepVars<Schemas["ReasonIn"]>) =>
      unwrap(api.POST("/api/v1/operations/runs/{run_id}/steps/{step_id}/skip", {
        params: { ...H, path: { run_id: runId, step_id: stepId } }, body, headers: idempotencyHeader(key),
      })),
    onSuccess: () => inv(),
    meta: { successMessage: "Step skipped" },
  });
}

export function useSucceedStep(runId: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: ({ stepId, body, key }: StepVars<Schemas["OptionalReasonIn"]>) =>
      unwrap(api.POST("/api/v1/operations/runs/{run_id}/steps/{step_id}/succeed", {
        params: { ...H, path: { run_id: runId, step_id: stepId } }, body, headers: idempotencyHeader(key),
      })),
    onSuccess: () => inv({ accounts: true }),
    meta: { successMessage: "Step marked as success" },
  });
}

export function useSignoffStep(runId: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (stepId: string) =>
      unwrap(api.POST("/api/v1/operations/runs/{run_id}/steps/{step_id}/signoff", { params: { ...H, path: { run_id: runId, step_id: stepId } } })),
    onSuccess: () => inv(),
    meta: { successMessage: "Signed off and locked" },
  });
}

export function useReopenStep(runId: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: ({ stepId, reason }: { stepId: string; reason: string }) =>
      unwrap(api.POST("/api/v1/operations/runs/{run_id}/steps/{step_id}/reopen", {
        params: { ...H, path: { run_id: runId, step_id: stepId } }, body: { reason },
      })),
    onSuccess: () => inv(),
    meta: { successMessage: "Step reopened (override recorded)" },
  });
}

export function usePostToRun(runId: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: ({ body, key }: { body: Schemas["RunPostingIn"]; key: string }) =>
      unwrap(api.POST("/api/v1/operations/runs/{run_id}/postings", { params: { ...H, path: { run_id: runId } }, body, headers: idempotencyHeader(key) })),
    onSuccess: () => inv({ accounts: true }),
    meta: { successMessage: "Voucher posted to this run" },
  });
}

export function useLinkVoucher(runId: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["LinkVoucherIn"]) =>
      unwrap(api.POST("/api/v1/operations/runs/{run_id}/linked-vouchers", { params: { ...H, path: { run_id: runId } }, body })),
    onSuccess: () => inv({ accounts: true }),
    meta: { successMessage: "Voucher linked" },
  });
}

export function useUnlinkVoucher(runId: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (voucherId: string) =>
      unwrap(api.DELETE("/api/v1/operations/runs/{run_id}/linked-vouchers/{voucher_id}", { params: { path: { run_id: runId, voucher_id: voucherId } } })),
    onSuccess: () => inv({ accounts: true }),
    meta: { successMessage: "Voucher unlinked" },
  });
}

export function useDossier(runId: string) {
  const { api } = useOrg();
  return useMutation({
    mutationFn: (format: "pdf" | "docx") =>
      unwrap(api.GET("/api/v1/operations/runs/{run_id}/dossier", { params: { path: { run_id: runId }, query: { format } }, parseAs: "blob" })),
  });
}
