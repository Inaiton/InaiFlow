import type { Metadata } from "next";
import { ItemsPage } from "@/features/operations/components/items/ItemsPage";

export const metadata: Metadata = { title: "Items & processes" };
export default function Page() {
  return <ItemsPage />;
}
