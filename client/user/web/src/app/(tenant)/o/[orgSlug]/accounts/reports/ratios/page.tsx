import type { Metadata } from "next";
import { Suspense } from "react";
import { RatiosPage } from "@/features/accounts/reports/ReportPages";

export const metadata: Metadata = { title: "Ratios" };
export default function Page() {
  return (
    <Suspense>
      <RatiosPage />
    </Suspense>
  );
}
