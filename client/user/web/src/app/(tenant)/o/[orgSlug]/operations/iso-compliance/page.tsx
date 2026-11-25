import type { Metadata } from "next";
import { Suspense } from "react";
import { IsoPage } from "@/features/operations/components/iso/IsoPage";

export const metadata: Metadata = { title: "ISO compliance" };
export default function Page() {
  return <Suspense><IsoPage /></Suspense>;
}
