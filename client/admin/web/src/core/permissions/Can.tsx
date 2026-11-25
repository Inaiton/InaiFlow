"use client";

import type { ReactNode } from "react";
import { useAuth } from "@/core/auth/AuthProvider";
import { adminCan, type AdminAction } from "./admin-can";

export function useAdminCan() {
  const { admin } = useAuth();
  return (action: AdminAction) => adminCan(admin?.role, action);
}

export function Can({ action, children, fallback = null }: { action: AdminAction; children: ReactNode; fallback?: ReactNode }) {
  const can = useAdminCan();
  return <>{can(action) ? children : fallback}</>;
}
