import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api/client";

export const systemKeys = { health: ["admin", "system", "health"] as const };

export function useSystemHealth(enabled = true) {
  return useQuery({
    queryKey: systemKeys.health,
    queryFn: () => unwrap(api.GET("/api/v1/admin/system/health")),
    enabled,
    staleTime: 60_000,
  });
}
