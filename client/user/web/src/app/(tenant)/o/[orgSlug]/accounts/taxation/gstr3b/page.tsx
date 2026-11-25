import type { Metadata } from "next";
import { Suspense } from "react";
import { Gstr3bPage } from "@/features/accounts/taxation/TaxPages";

export const metadata: Metadata = { title: "GSTR-3B" };
export default function Page() {
  return (
    <Suspense>
      <Gstr3bPage />
    </Suspense>
  );
}
