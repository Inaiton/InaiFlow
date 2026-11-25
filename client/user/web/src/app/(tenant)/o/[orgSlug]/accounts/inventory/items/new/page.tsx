import type { Metadata } from "next";
import { Suspense } from "react";
import { ItemEditor } from "@/features/accounts/inventory/ItemEditor";

export const metadata: Metadata = { title: "New stock item" };
export default function Page() {
  return (
    <Suspense>
      <ItemEditor />
    </Suspense>
  );
}
