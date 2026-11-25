import type { Metadata } from "next";
import { Suspense } from "react";
import { TemplatesPage } from "@/features/documents/components/templates/TemplatesPage";

export const metadata: Metadata = { title: "Templates" };
export default function Page() {
  return <Suspense><TemplatesPage /></Suspense>;
}
