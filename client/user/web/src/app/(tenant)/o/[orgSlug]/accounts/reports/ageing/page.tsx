import type { Metadata } from "next";
import { Suspense } from "react";
import { AgeingPage } from "@/features/accounts/reports/MoreReports";

export const metadata: Metadata = { title: "Ageing" };
export default function Page() {
  return (
    <Suspense>
      <AgeingPage />
    </Suspense>
  );
}
