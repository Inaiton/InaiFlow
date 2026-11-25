import type { Metadata } from "next";
import { Suspense } from "react";
import { GstSummaryPage } from "@/features/accounts/taxation/TaxPages";

export const metadata: Metadata = { title: "GST summary" };
export default function Page() {
  return (
    <Suspense>
      <GstSummaryPage />
    </Suspense>
  );
}
