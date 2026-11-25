import type { Metadata } from "next";
import { Suspense } from "react";
import { ReportNewPage } from "@/features/documents/components/reports/ReportNewPage";

export const metadata: Metadata = { title: "New inspection report" };
export default function Page() {
  return <Suspense><ReportNewPage /></Suspense>;
}
