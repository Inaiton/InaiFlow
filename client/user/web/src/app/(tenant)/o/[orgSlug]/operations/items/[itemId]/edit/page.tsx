import type { Metadata } from "next";
import { ItemEdit } from "@/features/operations/components/items/ItemEdit";

export const metadata: Metadata = { title: "Edit item" };
export default async function Page({ params }: { params: Promise<{ itemId: string }> }) {
  const { itemId } = await params;
  return <ItemEdit itemId={itemId} />;
}
