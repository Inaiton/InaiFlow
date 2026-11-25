"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { H } from "./params";
import { useOpsInvalidate, useOpsKey } from "./keys";

export function useOpsDashboard() {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({ queryKey: key("dashboard"), queryFn: () => unwrap(api.GET("/api/v1/operations/dashboard")) });
}

export type NcrQuery = { status?: string; period_run_id?: string; limit: number; offset: number };

export function useNcrs(query: NcrQuery, enabled = true) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("ncr", query),
    queryFn: () => unwrap(api.GET("/api/v1/operations/ncr", { params: { query } })),
    placeholderData: (prev) => prev,
    enabled,
  });
}

export function useNcr(id: string | null) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("ncr", "one", id),
    queryFn: () => unwrap(api.GET("/api/v1/operations/ncr/{ncr_id}", { params: { path: { ncr_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useCreateNcr() {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["NcrIn"]) => unwrap(api.POST("/api/v1/operations/ncr", { params: H, body })),
    onSuccess: () => inv(),
    meta: { successMessage: "NCR raised" },
  });
}

export function useUpdateNcr(id: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["NcrUpdateIn"]) => unwrap(api.PATCH("/api/v1/operations/ncr/{ncr_id}", { params: { path: { ncr_id: id } }, body })),
    onSuccess: () => inv(),
    meta: { successMessage: "NCR updated" },
  });
}

export function useCloseNcr(id: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["NcrCloseIn"]) => unwrap(api.POST("/api/v1/operations/ncr/{ncr_id}/close", { params: { ...H, path: { ncr_id: id } }, body })),
    onSuccess: () => inv(),
    meta: { successMessage: "NCR verified and closed" },
  });
}

export function useInstruments(status?: string, enabled = true) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("instruments", status ?? "all"),
    queryFn: () => unwrap(api.GET("/api/v1/operations/instruments", { params: { query: status ? { status } : {} } })),
    enabled,
  });
}

export function useSaveInstrument(id?: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["InstrumentIn"]) =>
      id
        ? unwrap(api.PATCH("/api/v1/operations/instruments/{instrument_id}", { params: { path: { instrument_id: id } }, body }))
        : unwrap(api.POST("/api/v1/operations/instruments", { params: H, body })),
    onSuccess: () => inv(),
    meta: { successMessage: id ? "Instrument saved" : "Instrument added" },
  });
}

export function useCalibrate(id: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["CalibrateIn"]) =>
      unwrap(api.POST("/api/v1/operations/instruments/{instrument_id}/calibrate", { params: { ...H, path: { instrument_id: id } }, body })),
    onSuccess: () => inv(),
    meta: { successMessage: "Calibration recorded" },
  });
}

export function useChecklist() {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({ queryKey: key("iso-checklist"), queryFn: () => unwrap(api.GET("/api/v1/operations/iso/checklist")) });
}

export function useUpdateChecklist() {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["ChecklistUpdateIn"] }) =>
      unwrap(api.PATCH("/api/v1/operations/iso/checklist/{item_id}", { params: { path: { item_id: id } }, body })),
    onSuccess: () => inv(),
    meta: { successMessage: "Checklist updated" },
  });
}

export function useReadiness() {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({ queryKey: key("iso-readiness"), queryFn: () => unwrap(api.GET("/api/v1/operations/iso/readiness")) });
}

export function useAuditorInvite() {
  const { api } = useOrg();
  return useMutation({
    mutationFn: (body: Schemas["AuditorInviteIn"]) => unwrap(api.POST("/api/v1/operations/iso/auditor-invites", { params: H, body })),
    meta: { successMessage: "Auditor invited" },
  });
}
