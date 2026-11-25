"use client";

import { useOrg } from "@/core/org/OrgProvider";

/** `/o/<slug>/operations…` link builder. */
export function useOpsPath() {
  const { slug } = useOrg();
  return (p = "") => `/o/${slug}/operations${p}`;
}

/** Cross-module links (documents / accounts) from operations screens. */
export function useOrgPath() {
  const { slug } = useOrg();
  return (p: string) => `/o/${slug}${p}`;
}
