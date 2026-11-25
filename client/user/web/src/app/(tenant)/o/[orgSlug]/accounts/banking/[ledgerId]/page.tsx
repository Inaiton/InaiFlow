import type { Metadata } from "next";
import { Suspense } from "react";
import { BrsPage } from "@/features/accounts/banking/BrsPage";

export const metadata: Metadata = { title: "Bank reconciliation" };
export default async function Page({ params }: { params: Promise<{ ledgerId: string }> }) {
  const { ledgerId } = await params;
  return (
    <Suspense>
      <BrsPage ledgerId={ledgerId} />
    </Suspense>
  );
}
