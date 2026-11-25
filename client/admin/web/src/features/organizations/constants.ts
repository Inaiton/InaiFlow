import type { components } from "@/lib/api/schema";

type S = components["schemas"];
export type LifecycleAction = S["LifecycleAction"];
export type ImpersonationMode = S["ImpersonationMode"];
export type OrgStatus = S["OrgStatus"];
export const ORG_STATUSES = ["ACTIVE", "TRIAL", "SUSPENDED", "ARCHIVED"] as const satisfies readonly OrgStatus[];
export const INDUSTRIES = ["MANUFACTURING", "PRECISION_ENGINEERING", "TRADING", "SERVICES", "OTHER"] as const;
export const IMPERSONATION_MODES = ["READ_ONLY", "FULL_SUPPORT"] as const satisfies readonly ImpersonationMode[];
