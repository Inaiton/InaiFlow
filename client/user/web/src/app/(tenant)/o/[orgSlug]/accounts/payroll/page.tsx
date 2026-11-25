import type { Metadata } from "next";
import { Suspense } from "react";
import { PayRunsPage } from "@/features/accounts/payroll/PayRunsPage";

export const metadata: Metadata = { title: "Payroll" };
export default function Page() {
  return (
    <Suspense>
      <PayRunsPage />
    </Suspense>
  );
}
