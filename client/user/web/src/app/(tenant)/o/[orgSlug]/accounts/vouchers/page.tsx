import type { Metadata } from "next";
import { Suspense } from "react";
import { VoucherRegister } from "@/features/accounts/vouchers/VoucherRegister";

export const metadata: Metadata = { title: "Vouchers" };
export default function Page() {
  return (
    <Suspense>
      <VoucherRegister />
    </Suspense>
  );
}
