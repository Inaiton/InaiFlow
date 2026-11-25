import type { Metadata } from "next";
import { Suspense } from "react";
import { Dashboard } from "@/features/accounts/gateway/Dashboard";

export const metadata: Metadata = { title: "Accounts · Overview" };
export default function Page() {
  return (
    <Suspense>
      <Dashboard />
    </Suspense>
  );
}
