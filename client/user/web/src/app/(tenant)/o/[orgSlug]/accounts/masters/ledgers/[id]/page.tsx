import type { Metadata } from "next";
import { Suspense } from "react";
import { LedgerDetail } from "@/features/accounts/masters/LedgerDetail";

export const metadata: Metadata = { title: "Ledger" };
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <LedgerDetail id={id} />
    </Suspense>
  );
}
