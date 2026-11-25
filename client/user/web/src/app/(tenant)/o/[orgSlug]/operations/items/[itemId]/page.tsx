import type { Metadata } from "next";
import { ItemDetail } from "@/features/operations/components/items/ItemDetail";

export const metadata: Metadata = { title: "Item" };
export default async function Page({ params }: { params: Promise<{ itemId: string }> }) {
  const { itemId } = await params;
  return <ItemDetail itemId={itemId} />;
}
