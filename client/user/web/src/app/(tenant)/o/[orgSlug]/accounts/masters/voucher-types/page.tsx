import type { Metadata } from "next";
import { Suspense } from "react";
import { VoucherTypesPage } from "@/features/accounts/masters/VoucherTypesPage";

export const metadata: Metadata = { title: "Voucher types" };
export default function Page() {
  return (
    <Suspense>
      <VoucherTypesPage />
    </Suspense>
  );
}
