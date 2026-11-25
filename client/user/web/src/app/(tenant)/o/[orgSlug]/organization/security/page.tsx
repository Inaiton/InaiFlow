import type { Metadata } from "next";
import { Suspense } from "react";
import { SecurityPage } from "@/features/organization/components/SecurityPage";

export const metadata: Metadata = { title: "Security" };
export default function Page() {
  return (
    <Suspense>
      <SecurityPage />
    </Suspense>
  );
}
