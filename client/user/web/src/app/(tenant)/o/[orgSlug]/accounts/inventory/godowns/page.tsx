import type { Metadata } from "next";
import { Suspense } from "react";
import { GodownsPage } from "@/features/accounts/inventory/GodownsGroupsPages";

export const metadata: Metadata = { title: "Godowns" };
export default function Page() {
  return (
    <Suspense>
      <GodownsPage />
    </Suspense>
  );
}
