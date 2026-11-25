import type { ReactNode } from "react";
import { TenantGate } from "@/features/tenant/TenantGate";

export default function TenantLayout({ children }: { children: ReactNode }) {
  return <TenantGate>{children}</TenantGate>;
}
