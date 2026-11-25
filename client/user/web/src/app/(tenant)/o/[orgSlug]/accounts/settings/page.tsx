import type { Metadata } from "next";
import { Suspense } from "react";
import { AccountsSettingsPage } from "@/features/accounts/masters/SettingsPage";

export const metadata: Metadata = { title: "Accounts settings" };
export default function Page() {
  return (
    <Suspense>
      <AccountsSettingsPage />
    </Suspense>
  );
}
