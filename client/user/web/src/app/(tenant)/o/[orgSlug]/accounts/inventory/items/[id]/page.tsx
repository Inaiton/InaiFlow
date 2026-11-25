import type { Metadata } from "next";
import { Suspense } from "react";
import { ItemDetail } from "@/features/accounts/inventory/ItemDetail";

export const metadata: Metadata = { title: "Stock item" };
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <ItemDetail id={id} />
    </Suspense>
  );
}
