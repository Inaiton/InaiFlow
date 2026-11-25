import type { Metadata } from "next";
import { OpsDashboard } from "@/features/operations/components/dashboard/OpsDashboard";

export const metadata: Metadata = { title: "Operations" };
export default function Page() {
  return <OpsDashboard />;
}
