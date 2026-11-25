"use client";

import { useQuery } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import { monthKey } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { useDocKey } from "../api/keys";

/**
 * Resolve the current month's system folder (e.g. kind "BILLS" → /FY 2026-27/11 - Nov 2026/Bills & Vouchers)
 * by walking root → FY → month → system kind. Returns null when the tree doesn't exist yet.
 */
export function useCurrentMonthFolder(kind: string, enabled = true) {
  const { api } = useOrg();
  const key = useDocKey();
  const month = monthKey(new Date());
  return useQuery({
    queryKey: key("current-month-folder", kind, month),
    enabled,
    staleTime: 300_000,
    queryFn: async () => {
      const list = (parent?: string) => unwrap(api.GET("/api/v1/documents/folders", { params: { query: parent ? { parent_id: parent } : {} } }));
      const roots = await list();
      for (const fy of roots.filter((f) => f.fy_label)) {
        const months = await list(fy.id);
        const m = months.find((f) => f.month_date?.slice(0, 7) === month);
        if (!m) continue;
        const kids = await list(m.id);
        return kids.find((f) => f.system_kind === kind) ?? m;
      }
      return null;
    },
  });
}
