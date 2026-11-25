import type { Metadata } from "next";
import { Suspense } from "react";
import { ItemEditor } from "@/features/accounts/inventory/ItemEditor";

export const metadata: Metadata = { title: "Alter stock item" };
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <ItemEditor id={id} />
    </Suspense>
  );
}
