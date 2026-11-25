import type { Metadata } from "next";
import { Suspense } from "react";
import { CashFlowPage } from "@/features/accounts/reports/ReportPages";

export const metadata: Metadata = { title: "Cash flow" };
export default function Page() {
  return (
    <Suspense>
      <CashFlowPage />
    </Suspense>
  );
}
