import type { Metadata } from "next";
import { Suspense } from "react";
import { LedgersPage } from "@/features/accounts/masters/LedgersPage";

export const metadata: Metadata = { title: "Ledgers" };
export default function Page() {
  return (
    <Suspense>
      <LedgersPage />
    </Suspense>
  );
}
