"use client";

import type { ReactNode } from "react";
import { useOptionalOrg } from "@/core/org/OrgProvider";
import { hasLevel, resolveLevel, type Level } from "./levels";

/** Effective level for a permission key in the active org ("module.*" = max of the module). */
export function usePermission(key: string): Level {
  const org = useOptionalOrg();
  return resolveLevel(org?.context ?? null, key);
}

/** `const canWrite = useCan("accounts.vouchers", "WRITE")` */
export function useCan(key: string, min: Level = "READ"): boolean {
  return hasLevel(usePermission(key), min);
}

interface CanProps {
  permission: string;
  level?: Level;
  fallback?: ReactNode;
  children: ReactNode;
}

/**
 * Render children only when the user has at least `level` on `permission`.
 *   <Can permission="accounts.vouchers" level="WRITE" fallback={null}><Button>New voucher</Button></Can>
 * Never check role codes in components — always gate on permission keys.
 */
export function Can({ permission, level = "READ", fallback = null, children }: CanProps) {
  return <>{useCan(permission, level) ? children : fallback}</>;
}
