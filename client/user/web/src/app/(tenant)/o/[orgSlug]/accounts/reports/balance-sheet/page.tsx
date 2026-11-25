import type { Metadata } from "next";
import { Suspense } from "react";
import { BalanceSheetPage } from "@/features/accounts/reports/ReportPages";

export const metadata: Metadata = { title: "Balance sheet" };
export default function Page() {
  return (
    <Suspense>
      <BalanceSheetPage />
    </Suspense>
  );
}
