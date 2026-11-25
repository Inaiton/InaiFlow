import type { Metadata } from "next";
import { Suspense } from "react";
import { VoucherView } from "@/features/accounts/vouchers/view/VoucherView";

export const metadata: Metadata = { title: "Voucher" };
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <VoucherView id={id} />
    </Suspense>
  );
}
