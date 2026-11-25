"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { idempotencyHeader, unwrap } from "@/core/api/client";
import type { ApiPaths, Schemas } from "@/core/api/types";
import { useAcc } from "../lib/api-base";
import { fetchFile } from "../lib/download";

export type Employee = Schemas["EmployeeOut"];
export type EmployeeQuery = NonNullable<ApiPaths["/api/v1/accounts/payroll/employees"]["get"]["parameters"]["query"]>;

export function useEmployees(query: EmployeeQuery) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("payroll", "employees", query), queryFn: () => unwrap(api.GET("/api/v1/accounts/payroll/employees", { params: { query } })), placeholderData: keepPreviousData });
}

export function useEmployee(id: string | null | undefined) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("payroll", "employee", id),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/payroll/employees/{employee_id}", { params: { path: { employee_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useSaveEmployee() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["EmployeeIn"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/accounts/payroll/employees/{employee_id}", { params: { path: { employee_id: id } }, body }))
        : unwrap(api.POST("/api/v1/accounts/payroll/employees", { body })),
    onSuccess: () => invalidate("payroll"),
    meta: { successMessage: "Employee saved" },
  });
}

export function useExitEmployee() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, date }: { id: string; date: string }) =>
      unwrap(api.POST("/api/v1/accounts/payroll/employees/{employee_id}/exit", { params: { path: { employee_id: id } }, body: { date_of_exit: date } })),
    onSuccess: () => invalidate("payroll"),
    meta: { successMessage: "Employee exit recorded" },
  });
}

export function usePayrollSettings() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("payroll", "settings"), queryFn: () => unwrap(api.GET("/api/v1/accounts/payroll/settings")) });
}

export function useSavePayrollSettings() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (body: Schemas["PayrollSettingsIn"]) => unwrap(api.PUT("/api/v1/accounts/payroll/settings", { body })),
    onSuccess: () => invalidate("payroll", "settings"),
    meta: { successMessage: "Payroll settings saved" },
  });
}

export function useAttendance(month: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("payroll", "attendance", month), queryFn: () => unwrap(api.GET("/api/v1/accounts/payroll/attendance", { params: { query: { month } } })) });
}

export function useSaveAttendance() {
  const { api, key, qc } = useAcc();
  return useMutation({
    mutationFn: (body: Schemas["AttendanceIn"]) => unwrap(api.PUT("/api/v1/accounts/payroll/attendance", { body })),
    onSuccess: (data) => qc.setQueryData(key("payroll", "attendance", data.month), data),
    meta: { successMessage: "Attendance saved" },
  });
}

export function usePullOperations() {
  const { api, key, qc } = useAcc();
  return useMutation({
    mutationFn: (month: string) => unwrap(api.POST("/api/v1/accounts/payroll/attendance/pull-operations", { params: { query: { month } } })),
    onSuccess: (data) => qc.setQueryData(key("payroll", "attendance", data.month), data),
    meta: { successMessage: "Production units pulled from Operations" },
  });
}

export function usePayrollRuns() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("payroll", "runs"), queryFn: () => unwrap(api.GET("/api/v1/accounts/payroll/runs")) });
}

export function usePayrollRun(id: string) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("payroll", "run", id), queryFn: () => unwrap(api.GET("/api/v1/accounts/payroll/runs/{run_id}", { params: { path: { run_id: id } } })) });
}

export function useCreatePayrollRun() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (month: string) => unwrap(api.POST("/api/v1/accounts/payroll/runs", { body: { month } })),
    onSuccess: () => invalidate("payroll", "runs"),
    meta: { successMessage: "Payroll run created" },
  });
}

/** recompute / lock / mark-paid / delete. Lock carries an Idempotency-Key (plan §7.2). */
export function usePayrollRunAction(id: string) {
  const { api, invalidate } = useAcc();
  const p = { params: { path: { run_id: id } } };
  return useMutation({
    mutationFn: async (a: { kind: "recompute" } | { kind: "lock"; key: string } | { kind: "paid"; body: Schemas["MarkPaidIn"] } | { kind: "delete" }) => {
      if (a.kind === "recompute") return unwrap(api.POST("/api/v1/accounts/payroll/runs/{run_id}/recompute", p));
      if (a.kind === "lock") return unwrap(api.POST("/api/v1/accounts/payroll/runs/{run_id}/lock", { params: { path: { run_id: id }, header: idempotencyHeader(a.key) } }));
      if (a.kind === "paid") return unwrap(api.POST("/api/v1/accounts/payroll/runs/{run_id}/mark-paid", { ...p, body: a.body }));
      await unwrap(api.DELETE("/api/v1/accounts/payroll/runs/{run_id}", { params: { path: { run_id: id } } }));
      return null;
    },
    onSuccess: () => invalidate(),
  });
}

export function usePayrollFile() {
  const { api } = useAcc();
  return useMutation({
    mutationFn: (f: { kind: "bank"; runId: string } | { kind: "payslip"; runId: string; lineId: string } | { kind: "statutory"; runId: string; statutory: string }) => {
      if (f.kind === "bank") return fetchFile(api.GET("/api/v1/accounts/payroll/runs/{run_id}/bank-file", { params: { path: { run_id: f.runId }, query: { format: "csv" } }, parseAs: "blob" }), "salary-bank-file.csv");
      if (f.kind === "payslip")
        return fetchFile(api.GET("/api/v1/accounts/payroll/runs/{run_id}/payslips/{line_id}", { params: { path: { run_id: f.runId, line_id: f.lineId } }, parseAs: "blob" }), "payslip.pdf", "open");
      return fetchFile(api.GET("/api/v1/accounts/payroll/runs/{run_id}/statutory/{kind}", { params: { path: { run_id: f.runId, kind: f.statutory } }, parseAs: "blob" }), `${f.statutory}.txt`);
    },
  });
}

/** Period runs for allocation pickers (Operations module, read-only). */
export function usePeriodRuns(month: string | undefined, enabled = true) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("period-runs", month),
    queryFn: () => unwrap(api.GET("/api/v1/operations/runs", { params: { query: { ...(month ? { period_month: month } : {}), limit: 200 } } })),
    enabled,
    staleTime: 60_000,
  });
}
