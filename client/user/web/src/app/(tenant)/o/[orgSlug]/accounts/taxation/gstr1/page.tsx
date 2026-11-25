import type { Metadata } from "next";
import { Suspense } from "react";
import { Gstr1Page } from "@/features/accounts/taxation/TaxPages";

export const metadata: Metadata = { title: "GSTR-1" };
export default function Page() {
  return (
    <Suspense>
      <Gstr1Page />
    </Suspense>
  );
}
