import type { Metadata } from "next";
import { Suspense } from "react";
import { ChequesPage } from "@/features/accounts/banking/ChequesPage";

export const metadata: Metadata = { title: "Cheques" };
export default function Page() {
  return (
    <Suspense>
      <ChequesPage />
    </Suspense>
  );
}
