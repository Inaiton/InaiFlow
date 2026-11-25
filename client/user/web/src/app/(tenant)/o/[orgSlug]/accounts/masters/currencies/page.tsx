import type { Metadata } from "next";
import { Suspense } from "react";
import { CurrenciesPage } from "@/features/accounts/masters/CurrenciesPage";

export const metadata: Metadata = { title: "Currencies" };
export default function Page() {
  return (
    <Suspense>
      <CurrenciesPage />
    </Suspense>
  );
}
