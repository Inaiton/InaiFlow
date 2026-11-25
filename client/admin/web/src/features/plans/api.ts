import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export const planKeys = { all: ["admin", "plans"] as const };

export function usePlans() {
  return useQuery({ queryKey: planKeys.all, queryFn: () => unwrap(api.GET("/api/v1/admin/plans")) });
}

export function useCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["PlanIn"]) => unwrap(api.POST("/api/v1/admin/plans", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: planKeys.all }),
  });
}

export function useUpdatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["PlanUpdateIn"] }) =>
      unwrap(api.PATCH("/api/v1/admin/plans/{plan_id}", { params: { path: { plan_id: id } }, body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: planKeys.all }),
  });
}
