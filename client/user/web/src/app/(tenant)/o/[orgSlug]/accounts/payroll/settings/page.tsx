import type { Metadata } from "next";
import { Suspense } from "react";
import { PayrollSettingsPage } from "@/features/accounts/payroll/PayrollSettingsPage";

export const metadata: Metadata = { title: "Payroll settings" };
export default function Page() {
  return (
    <Suspense>
      <PayrollSettingsPage />
    </Suspense>
  );
}
