import type { Metadata } from "next";
import { Suspense } from "react";
import { VoucherEditPage } from "@/features/accounts/vouchers/VoucherNewPage";

export const metadata: Metadata = { title: "Alter voucher" };
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <VoucherEditPage id={id} />
    </Suspense>
  );
}
