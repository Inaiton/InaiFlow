import type { Metadata } from "next";
import { Suspense } from "react";
import { LedgerEditor } from "@/features/accounts/masters/LedgerEditor";

export const metadata: Metadata = { title: "New ledger" };
export default function Page() {
  return (
    <Suspense>
      <LedgerEditor />
    </Suspense>
  );
}
