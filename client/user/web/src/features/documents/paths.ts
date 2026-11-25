"use client";

import { useOrg } from "@/core/org/OrgProvider";

/** `/o/<slug>/documents…` link builder. */
export function useDocsPath() {
  const { slug } = useOrg();
  return (p = "") => `/o/${slug}/documents${p}`;
}
