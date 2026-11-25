"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import type { ApiPaths, Schemas } from "@/core/api/types";
import { uploadToTicket } from "@/core/upload";
import { useAcc } from "../lib/api-base";

export type StockItem = Schemas["StockItemOut"];
export type ItemQuery = NonNullable<ApiPaths["/api/v1/accounts/stock-items"]["get"]["parameters"]["query"]>;
export type SummaryQuery = NonNullable<ApiPaths["/api/v1/accounts/inventory/stock-summary"]["get"]["parameters"]["query"]>;

export function useGodowns(enabled = true) {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("godowns"), queryFn: () => unwrap(api.GET("/api/v1/accounts/godowns")), staleTime: 60_000, enabled });
}

export function useSaveGodown() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["GodownIn"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/accounts/godowns/{godown_id}", { params: { path: { godown_id: id } }, body }))
        : unwrap(api.POST("/api/v1/accounts/godowns", { body })),
    onSuccess: () => invalidate("godowns"),
    meta: { successMessage: "Godown saved" },
  });
}

export function useDeleteGodown() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/accounts/godowns/{godown_id}", { params: { path: { godown_id: id } } })),
    onSuccess: () => invalidate("godowns"),
    meta: { successMessage: "Godown deleted" },
  });
}

export function useStockGroups() {
  const { api, key } = useAcc();
  return useQuery({ queryKey: key("stock-groups"), queryFn: () => unwrap(api.GET("/api/v1/accounts/stock-groups")), staleTime: 60_000 });
}

export function useSaveStockGroup() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["StockGroupIn"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/accounts/stock-groups/{stock_group_id}", { params: { path: { stock_group_id: id } }, body }))
        : unwrap(api.POST("/api/v1/accounts/stock-groups", { body })),
    onSuccess: () => invalidate("stock-groups"),
    meta: { successMessage: "Stock group saved" },
  });
}

export function useDeleteStockGroup() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/accounts/stock-groups/{stock_group_id}", { params: { path: { stock_group_id: id } } })),
    onSuccess: () => invalidate("stock-groups"),
    meta: { successMessage: "Stock group deleted" },
  });
}

export function useStockItems(query: ItemQuery, enabled = true) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("stock-items", "list", query),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/stock-items", { params: { query } })),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useStockItem(id: string | null | undefined) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("stock-items", "one", id),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/stock-items/{item_id}", { params: { path: { item_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useSaveStockItem() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["StockItemIn"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/accounts/stock-items/{item_id}", { params: { path: { item_id: id } }, body }))
        : unwrap(api.POST("/api/v1/accounts/stock-items", { body })),
    onSuccess: () => {
      void invalidate("stock-items");
      void invalidate("stock-summary");
    },
    meta: { successMessage: "Stock item saved" },
  });
}

export function useDeleteStockItem() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/accounts/stock-items/{item_id}", { params: { path: { item_id: id } } })),
    onSuccess: () => invalidate("stock-items"),
    meta: { successMessage: "Stock item deleted" },
  });
}

/** Upload an engineering diagram; resolves to the storage key for `diagram_storage_key`. */
export function useUploadDiagram() {
  const { api } = useAcc();
  return useMutation({
    mutationFn: async (file: File) => {
      const ticket = await unwrap(api.POST("/api/v1/accounts/stock-items/upload-url", { body: { content_type: file.type, size_bytes: file.size, file_name: file.name } }));
      await uploadToTicket(ticket, file, file.name);
      return ticket.storage_key;
    },
  });
}

export function useStockSummary(query: SummaryQuery) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("stock-summary", query),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/inventory/stock-summary", { params: { query } })),
    placeholderData: keepPreviousData,
  });
}

export function useItemMovements(id: string, from: string, to: string, godownId?: string) {
  const { api, key } = useAcc();
  return useQuery({
    queryKey: key("stock-items", "movements", id, from, to, godownId),
    queryFn: () =>
      unwrap(api.GET("/api/v1/accounts/inventory/items/{item_id}/movements", {
        params: { path: { item_id: id }, query: { date_from: from, date_to: to, ...(godownId ? { godown_id: godownId } : {}) } },
      })),
    placeholderData: keepPreviousData,
  });
}
