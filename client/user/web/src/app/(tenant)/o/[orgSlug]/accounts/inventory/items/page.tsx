import type { Metadata } from "next";
import { Suspense } from "react";
import { ItemsPage } from "@/features/accounts/inventory/ItemsPage";

export const metadata: Metadata = { title: "Stock items" };
export default function Page() {
  return (
    <Suspense>
      <ItemsPage />
    </Suspense>
  );
}
