import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export const configKeys = {
  all: ["admin", "configs"] as const,
  list: (category?: string) => ["admin", "configs", "list", category ?? "*"] as const,
  detail: (id: string) => ["admin", "configs", "detail", id] as const,
  history: (id: string) => ["admin", "configs", "history", id] as const,
};

export function useConfigs(category?: string) {
  return useQuery({ queryKey: configKeys.list(category), queryFn: () => unwrap(api.GET("/api/v1/admin/configs", { params: { query: { category } } })) });
}

export function useConfig(id: string) {
  return useQuery({ queryKey: configKeys.detail(id), queryFn: () => unwrap(api.GET("/api/v1/admin/configs/{config_id}", { params: { path: { config_id: id } } })) });
}

export function useConfigHistory(id: string, enabled: boolean) {
  return useQuery({
    queryKey: configKeys.history(id),
    queryFn: () => unwrap(api.GET("/api/v1/admin/configs/{config_id}/history", { params: { path: { config_id: id } } })),
    enabled,
  });
}

export function useCreateConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["ConfigIn"]) => unwrap(api.POST("/api/v1/admin/configs", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...configKeys.all, "list"] }),
  });
}

export function useUpdateConfig(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["ConfigUpdateIn"]) => unwrap(api.PUT("/api/v1/admin/configs/{config_id}", { params: { path: { config_id: id } }, body })),
    onSuccess: (data) => {
      qc.setQueryData(configKeys.detail(id), data);
      void qc.invalidateQueries({ queryKey: configKeys.history(id) });
      void qc.invalidateQueries({ queryKey: [...configKeys.all, "list"] });
    },
  });
}

export function usePushConfig(id: string) {
  return useMutation({
    mutationFn: (body: Schemas["ConfigPushIn"]) => unwrap(api.POST("/api/v1/admin/configs/{config_id}/push", { params: { path: { config_id: id } }, body })),
  });
}

export function usePermissionKeys() {
  return useQuery({ queryKey: ["meta", "permission-keys"], queryFn: () => unwrap(api.GET("/api/v1/meta/permission-keys")), staleTime: Infinity });
}

export function useTemplateTokens(enabled = true) {
  return useQuery({ queryKey: ["admin", "meta", "template-tokens"], queryFn: () => unwrap(api.GET("/api/v1/admin/meta/template-tokens")), staleTime: Infinity, enabled });
}
