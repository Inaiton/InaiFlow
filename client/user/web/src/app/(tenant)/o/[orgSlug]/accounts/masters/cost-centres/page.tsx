import type { Metadata } from "next";
import { Suspense } from "react";
import { CostCentresPage } from "@/features/accounts/masters/CostCentresPage";

export const metadata: Metadata = { title: "Cost centres" };
export default function Page() {
  return (
    <Suspense>
      <CostCentresPage />
    </Suspense>
  );
}
