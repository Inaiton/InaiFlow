import type { ReactNode } from "react";
import { AuthShell } from "@/components/shell/AuthShell";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return <AuthShell>{children}</AuthShell>;
}
