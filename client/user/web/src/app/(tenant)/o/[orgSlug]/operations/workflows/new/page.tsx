import type { Metadata } from "next";
import { Suspense } from "react";
import { NewWorkflowPage } from "@/features/operations/components/workflows/NewWorkflowPage";

export const metadata: Metadata = { title: "New workflow" };
export default function Page() {
  return <Suspense><NewWorkflowPage /></Suspense>;
}
