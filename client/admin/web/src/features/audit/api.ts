import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api/client";

export interface AuditFilters {
  action?: string;
  target_type?: string;
  admin_id?: string;
  date_from?: string;
  date_to?: string;
  limit: number;
  offset: number;
}

export function useAuditLogs(f: AuditFilters) {
  const query = Object.fromEntries(Object.entries(f).filter(([, v]) => v !== "" && v !== undefined)) as AuditFilters;
  return useQuery({
    queryKey: ["admin", "audit", f],
    queryFn: () => unwrap(api.GET("/api/v1/admin/audit-logs", { params: { query } })),
    placeholderData: keepPreviousData,
  });
}
