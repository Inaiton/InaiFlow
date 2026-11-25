"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { useDocInvalidate, useDocKey } from "./keys";
import { H } from "./params";

export type FolderOut = Schemas["FolderOut"];

/** Children of a folder (root when parentId is null). Lazy per tree level. */
export function useFolders(parentId: string | null, enabled = true) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("folders", parentId ?? "root"),
    queryFn: () => unwrap(api.GET("/api/v1/documents/folders", { params: { query: parentId ? { parent_id: parentId } : {} } })),
    enabled,
    staleTime: 30_000,
  });
}

export function useFolder(id: string | null) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("folder", id),
    queryFn: () => unwrap(api.GET("/api/v1/documents/folders/{folder_id}", { params: { path: { folder_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useFolderPath(id: string | null) {
  const { api } = useOrg();
  const key = useDocKey();
  return useQuery({
    queryKey: key("folder", id, "path"),
    queryFn: () => unwrap(api.GET("/api/v1/documents/folders/{folder_id}/path", { params: { path: { folder_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useCreateFolder() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["FolderIn"]) => unwrap(api.POST("/api/v1/documents/folders", { params: H, body })),
    onSuccess: () => inv("folders"),
    meta: { successMessage: "Folder created" },
  });
}

export function useUpdateFolder() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["FolderUpdateIn"] }) =>
      unwrap(api.PATCH("/api/v1/documents/folders/{folder_id}", { params: { path: { folder_id: id } }, body })),
    onSuccess: () => inv(),
    meta: { successMessage: "Folder updated" },
  });
}

export function useDeleteFolder() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/documents/folders/{folder_id}", { params: { path: { folder_id: id } } })),
    onSuccess: () => inv(),
    meta: { successMessage: "Folder deleted" },
  });
}

export function useEnsureMonth() {
  const { api } = useOrg();
  const inv = useDocInvalidate();
  return useMutation({
    mutationFn: (month: string) => unwrap(api.POST("/api/v1/documents/folders/ensure-month", { params: H, body: { month } })),
    onSuccess: () => inv("folders"),
    meta: { successMessage: "Month folders are ready" },
  });
}
