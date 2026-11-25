import type { ReactNode } from "react";
import { RequireAuth } from "@/core/auth/RequireAuth";
import { PersonalShell } from "@/components/shell/AppShell";

export default function PersonalLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth allowImpersonation={false}>
      <PersonalShell>{children}</PersonalShell>
    </RequireAuth>
  );
}
