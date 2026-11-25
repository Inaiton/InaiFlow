import type { ReactNode } from "react";
import { AccountsLayout } from "@/features/accounts/shell/AccountsLayout";

export default function Layout({ children }: { children: ReactNode }) {
  return <AccountsLayout>{children}</AccountsLayout>;
}
