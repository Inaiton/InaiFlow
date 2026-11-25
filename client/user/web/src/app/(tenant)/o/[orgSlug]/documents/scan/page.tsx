import type { Metadata } from "next";
import { Suspense } from "react";
import { ScanPage } from "@/features/documents/components/scan/ScanPage";

export const metadata: Metadata = { title: "Scanner" };
export default function Page() {
  return <Suspense><ScanPage /></Suspense>;
}
