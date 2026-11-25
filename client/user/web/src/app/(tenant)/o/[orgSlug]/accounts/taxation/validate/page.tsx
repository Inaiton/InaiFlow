import type { Metadata } from "next";
import { Suspense } from "react";
import { GstValidatePage } from "@/features/accounts/taxation/TaxPages";

export const metadata: Metadata = { title: "GST validator" };
export default function Page() {
  return (
    <Suspense>
      <GstValidatePage />
    </Suspense>
  );
}
