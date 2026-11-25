"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOrg } from "@/core/org/OrgProvider";
import { qk } from "@/core/query-keys";

export function useDocKey() {
  const { orgId } = useOrg();
  return (...rest: unknown[]) => qk.org(orgId, "documents", ...rest);
}

export function useDocInvalidate() {
  const qc = useQueryClient();
  const { orgId } = useOrg();
  return (...rest: unknown[]) => qc.invalidateQueries({ queryKey: qk.org(orgId, "documents", ...rest) });
}
