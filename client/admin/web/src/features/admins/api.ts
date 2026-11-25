import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "@/lib/api/client";

const key = ["admin", "admins"] as const;

export function useAdmins(enabled = true) {
  return useQuery({ queryKey: key, queryFn: () => unwrap(api.GET("/api/v1/admin/admins")), enabled });
}

export function useCreateAdmin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["AdminAccountIn"]) => unwrap(api.POST("/api/v1/admin/admins", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });
}

export function useUpdateAdmin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["AdminAccountUpdateIn"] }) => unwrap(api.PATCH("/api/v1/admin/admins/{admin_id}", { params: { path: { admin_id: id } }, body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });
}
