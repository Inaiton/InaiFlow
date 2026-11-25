"use client";

import { useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import { useOrg } from "@/core/org/OrgProvider";
import { qk } from "@/core/query-keys";
import type { ComboboxOption } from "@/components/ui";

export const RESOURCE_TYPES = [
  { value: "STOCK_ITEM", label: "Stock item" },
  { value: "PERIOD_RUN", label: "Period run" },
  { value: "DOC_FOLDER", label: "Document folder" },
  { value: "GODOWN", label: "Godown" },
] as const;
export type ResourceType = (typeof RESOURCE_TYPES)[number]["value"];

/**
 * Name lookup for ACL resources via the owning modules' list endpoints. Needs READ on that module;
 * when it fails the builder falls back to pasting a record id.
 */
export function useResourceOptions(type: ResourceType, q: string) {
  const { api, orgId } = useOrg();
  return useQuery({
    queryKey: qk.org(orgId, "organization", "acl-lookup", type, q),
    meta: { silentError: true },
    retry: false,
    queryFn: async (): Promise<ComboboxOption[]> => {
      const query = q.trim() ? { q: q.trim(), limit: 20 } : { limit: 20 };
      switch (type) {
        case "STOCK_ITEM": {
          const p = await unwrap(api.GET("/api/v1/accounts/stock-items", { params: { query } }));
          return p.items.map((i) => ({ value: i.id, label: i.name, hint: i.sku_code ?? undefined }));
        }
        case "PERIOD_RUN": {
          const p = await unwrap(api.GET("/api/v1/operations/runs", { params: { query } }));
          return p.items.map((r) => ({ value: r.id, label: r.run_title, hint: r.status }));
        }
        case "DOC_FOLDER": {
          const list = await unwrap(api.GET("/api/v1/documents/folders"));
          return list.filter((f) => !q || f.name.toLowerCase().includes(q.toLowerCase())).map((f) => ({ value: f.id, label: f.name, hint: f.fy_label ?? undefined }));
        }
        case "GODOWN": {
          const list = await unwrap(api.GET("/api/v1/accounts/godowns"));
          return list.filter((g) => !q || g.name.toLowerCase().includes(q.toLowerCase())).map((g) => ({ value: g.id, label: g.name, hint: g.godown_type }));
        }
      }
    },
  });
}
