import type { Metadata } from "next";
import { Suspense } from "react";
import { UtilitiesPage } from "@/features/accounts/utilities/UtilitiesPage";

export const metadata: Metadata = { title: "Utilities" };
export default function Page() {
  return (
    <Suspense>
      <UtilitiesPage />
    </Suspense>
  );
}
