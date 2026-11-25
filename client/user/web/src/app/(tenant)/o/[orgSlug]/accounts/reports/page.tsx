import type { Metadata } from "next";
import { Suspense } from "react";
import { ReportsHub } from "@/features/accounts/reports/MoreReports";

export const metadata: Metadata = { title: "Reports" };
export default function Page() {
  return (
    <Suspense>
      <ReportsHub />
    </Suspense>
  );
}
