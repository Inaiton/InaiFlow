import type { Metadata } from "next";
import { WorkflowEditor } from "@/features/operations/components/workflows/WorkflowEditor";

export const metadata: Metadata = { title: "Workflow studio" };
export default async function Page({ params }: { params: Promise<{ workflowId: string }> }) {
  const { workflowId } = await params;
  return <WorkflowEditor workflowId={workflowId} />;
}
