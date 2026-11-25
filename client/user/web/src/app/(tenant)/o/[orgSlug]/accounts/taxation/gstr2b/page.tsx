import type { Metadata } from "next";
import { Suspense } from "react";
import { Gstr2bPage } from "@/features/accounts/taxation/Gstr2bPage";

export const metadata: Metadata = { title: "GSTR-2B reconciliation" };
export default function Page() {
  return (
    <Suspense>
      <Gstr2bPage />
    </Suspense>
  );
}
