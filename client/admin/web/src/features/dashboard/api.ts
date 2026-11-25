import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api/client";

export function useDashboard() {
  return useQuery({ queryKey: ["admin", "dashboard"], queryFn: () => unwrap(api.GET("/api/v1/admin/dashboard")), refetchInterval: 60_000 });
}
