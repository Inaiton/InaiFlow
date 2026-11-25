import type { Metadata } from "next";
import { RunWorkspace } from "@/features/operations/components/runs/RunWorkspace";

export const metadata: Metadata = { title: "Run workspace" };
export default async function Page({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <RunWorkspace runId={runId} />;
}
