import type { Metadata } from "next";
import { Suspense } from "react";
import { LedgerEditor } from "@/features/accounts/masters/LedgerEditor";

export const metadata: Metadata = { title: "Alter ledger" };
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <LedgerEditor id={id} />
    </Suspense>
  );
}
