import type { Metadata } from "next";
import { Suspense } from "react";
import { BillingPage } from "@/features/organization/components/BillingPage";

export const metadata: Metadata = { title: "Billing" };
export default function Page() {
  return (
    <Suspense>
      <BillingPage />
    </Suspense>
  );
}
