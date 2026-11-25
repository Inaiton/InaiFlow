import type { Metadata } from "next";
import { Suspense } from "react";
import { BankAccountsPage } from "@/features/accounts/banking/BankAccountsPage";

export const metadata: Metadata = { title: "Banking" };
export default function Page() {
  return (
    <Suspense>
      <BankAccountsPage />
    </Suspense>
  );
}
