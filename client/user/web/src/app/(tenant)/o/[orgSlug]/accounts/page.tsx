import type { Metadata } from "next";
import { Suspense } from "react";
import { Gateway } from "@/features/accounts/gateway/Gateway";

export const metadata: Metadata = { title: "Accounts · Gateway" };
export default function Page() {
  return (
    <Suspense>
      <Gateway />
    </Suspense>
  );
}
