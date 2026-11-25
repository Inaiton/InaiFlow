import type { Metadata } from "next";
import { Suspense } from "react";
import { StockSummaryPage } from "@/features/accounts/inventory/StockSummaryPage";

export const metadata: Metadata = { title: "Stock summary" };
export default function Page() {
  return (
    <Suspense>
      <StockSummaryPage />
    </Suspense>
  );
}
