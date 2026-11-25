import type { Metadata } from "next";
import { Suspense } from "react";
import { MastersHub } from "@/features/accounts/masters/MastersHub";

export const metadata: Metadata = { title: "Masters" };
export default function Page() {
  return (
    <Suspense>
      <MastersHub />
    </Suspense>
  );
}
