import type { Metadata } from "next";
import { Suspense } from "react";
import { TrialBalancePage } from "@/features/accounts/reports/ReportPages";

export const metadata: Metadata = { title: "Trial balance" };
export default function Page() {
  return (
    <Suspense>
      <TrialBalancePage />
    </Suspense>
  );
}
