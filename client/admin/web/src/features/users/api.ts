import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export interface UserFilters {
  q?: string;
  suspended?: boolean;
  limit: number;
  offset: number;
}

export const userKeys = {
  all: ["admin", "users"] as const,
  list: (f: UserFilters) => ["admin", "users", "list", f] as const,
  detail: (id: string) => ["admin", "users", "detail", id] as const,
};

export function useUsers(f: UserFilters, enabled = true) {
  return useQuery({
    queryKey: userKeys.list(f),
    queryFn: () => unwrap(api.GET("/api/v1/admin/users", { params: { query: { ...f, q: f.q?.trim() || undefined } } })),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useUser(id: string, enabled = true) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => unwrap(api.GET("/api/v1/admin/users/{user_id}", { params: { path: { user_id: id } } })),
    enabled: enabled && !!id,
  });
}

export function useUserAction(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["UserActionIn"]) => unwrap(api.POST("/api/v1/admin/users/{user_id}/actions", { params: { path: { user_id: id } }, body })),
    onSuccess: (data) => {
      qc.setQueryData(userKeys.detail(id), data);
      void qc.invalidateQueries({ queryKey: [...userKeys.all, "list"] });
    },
  });
}
