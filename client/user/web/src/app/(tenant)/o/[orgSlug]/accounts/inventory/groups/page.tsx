import type { Metadata } from "next";
import { Suspense } from "react";
import { StockGroupsPage } from "@/features/accounts/inventory/GodownsGroupsPages";

export const metadata: Metadata = { title: "Stock groups" };
export default function Page() {
  return (
    <Suspense>
      <StockGroupsPage />
    </Suspense>
  );
}
