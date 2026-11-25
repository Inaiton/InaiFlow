import type { Metadata } from "next";
import { Suspense } from "react";
import { BatchCostingPage } from "@/features/accounts/reports/MoreReports";

export const metadata: Metadata = { title: "Batch costing" };
export default function Page() {
  return (
    <Suspense>
      <BatchCostingPage />
    </Suspense>
  );
}
