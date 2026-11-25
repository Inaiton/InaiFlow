import type { Metadata } from "next";
import { Suspense } from "react";
import { VoucherNewPage } from "@/features/accounts/vouchers/VoucherNewPage";

export const metadata: Metadata = { title: "New voucher" };
export default function Page() {
  return (
    <Suspense>
      <VoucherNewPage />
    </Suspense>
  );
}
