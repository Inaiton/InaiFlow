import type { Metadata } from "next";
import { Suspense } from "react";
import { ExplorerPage } from "@/features/documents/components/explorer/ExplorerPage";

export const metadata: Metadata = { title: "Documents" };
export default function Page() {
  return <Suspense><ExplorerPage /></Suspense>;
}
