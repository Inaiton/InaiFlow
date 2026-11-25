import type { Metadata } from "next";
import { Suspense } from "react";
import { PayRunDetail } from "@/features/accounts/payroll/PayRunDetail";

export const metadata: Metadata = { title: "Pay run" };
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <PayRunDetail id={id} />
    </Suspense>
  );
}
