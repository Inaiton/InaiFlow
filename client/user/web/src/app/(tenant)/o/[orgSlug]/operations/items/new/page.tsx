import type { Metadata } from "next";
import { ItemForm } from "@/features/operations/components/items/ItemForm";

export const metadata: Metadata = { title: "New item" };
export default function Page() {
  return <ItemForm />;
}
