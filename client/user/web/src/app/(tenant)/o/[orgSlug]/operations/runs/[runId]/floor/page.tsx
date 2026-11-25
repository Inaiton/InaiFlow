import type { Metadata } from "next";
import { FloorView } from "@/features/operations/components/runs/FloorView";

export const metadata: Metadata = { title: "Shop floor" };
export default async function Page({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <FloorView runId={runId} />;
}
