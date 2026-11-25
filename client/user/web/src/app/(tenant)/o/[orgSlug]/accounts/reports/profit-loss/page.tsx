import type { Metadata } from "next";
import { Suspense } from "react";
import { ProfitLossPage } from "@/features/accounts/reports/ReportPages";

export const metadata: Metadata = { title: "Profit & loss" };
export default function Page() {
  return (
    <Suspense>
      <ProfitLossPage />
    </Suspense>
  );
}
