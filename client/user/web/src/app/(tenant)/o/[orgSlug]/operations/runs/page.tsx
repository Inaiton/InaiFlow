import type { Metadata } from "next";
import { RunsPage } from "@/features/operations/components/runs/RunsPage";

export const metadata: Metadata = { title: "Period runs" };
export default function Page() {
  return <RunsPage />;
}
