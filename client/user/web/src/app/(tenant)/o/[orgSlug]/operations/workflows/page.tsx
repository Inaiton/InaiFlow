import type { Metadata } from "next";
import { WorkflowsPage } from "@/features/operations/components/workflows/WorkflowsPage";

export const metadata: Metadata = { title: "Workflow studio" };
export default function Page() {
  return <WorkflowsPage />;
}
