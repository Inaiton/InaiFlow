"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { uploadToTicket } from "@/core/upload";
import { H } from "./params";
import { useOpsInvalidate, useOpsKey } from "./keys";

export type ItemsQuery = { q?: string; target_type?: string; limit: number; offset: number };

export function useOpsItems(query: ItemsQuery) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("items", query),
    queryFn: () => unwrap(api.GET("/api/v1/operations/items", { params: { query } })),
    placeholderData: (prev) => prev,
  });
}

export function useOpsItem(itemId: string | null | undefined) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("item", itemId),
    queryFn: () => unwrap(api.GET("/api/v1/operations/items/{item_id}", { params: { path: { item_id: itemId! } } })),
    enabled: Boolean(itemId),
  });
}

export function useItemRuns(itemId: string) {
  const { api } = useOrg();
  const key = useOpsKey();
  return useQuery({
    queryKey: key("item", itemId, "runs"),
    queryFn: () => unwrap(api.GET("/api/v1/operations/items/{item_id}/runs", { params: { path: { item_id: itemId } } })),
  });
}

export function useSaveItem(itemId?: string) {
  const { api } = useOrg();
  const inv = useOpsInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["StockItemIn"]) =>
      itemId
        ? unwrap(api.PATCH("/api/v1/operations/items/{item_id}", { params: { path: { item_id: itemId } }, body }))
        : unwrap(api.POST("/api/v1/operations/items", { params: H, body })),
    onSuccess: () => inv({ accounts: true }),
    meta: { successMessage: itemId ? "Item saved" : "Item added" },
  });
}

/** Engineering diagram → `/accounts/stock-items/upload-url` ticket → raw PUT; returns the storage key. */
export function useUploadDiagram() {
  const { api } = useOrg();
  return useMutation({
    mutationFn: async (file: File) => {
      const ticket = await unwrap(api.POST("/api/v1/accounts/stock-items/upload-url", { params: H,
        body: { file_name: file.name, content_type: file.type || "application/octet-stream", size_bytes: file.size },
      }));
      await uploadToTicket(ticket, file, file.name);
      return ticket.storage_key;
    },
  });
}
