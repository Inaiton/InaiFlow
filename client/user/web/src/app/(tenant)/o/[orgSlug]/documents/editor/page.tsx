import type { Metadata } from "next";
import { ReportsIndex } from "@/features/documents/components/reports/ReportsIndex";

export const metadata: Metadata = { title: "Inspection reports" };
export default function Page() {
  return <ReportsIndex />;
}
