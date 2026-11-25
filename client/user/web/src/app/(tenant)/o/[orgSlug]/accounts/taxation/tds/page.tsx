import type { Metadata } from "next";
import { Suspense } from "react";
import { TdsPage } from "@/features/accounts/taxation/TdsPage";

export const metadata: Metadata = { title: "TDS / TCS" };
export default function Page() {
  return (
    <Suspense>
      <TdsPage />
    </Suspense>
  );
}
