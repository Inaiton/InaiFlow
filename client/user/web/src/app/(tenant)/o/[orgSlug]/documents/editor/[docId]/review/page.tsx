import type { Metadata } from "next";
import { ReportReviewPage } from "@/features/documents/components/reports/ReportReviewPage";

export const metadata: Metadata = { title: "Review & sign" };
export default async function Page({ params }: { params: Promise<{ docId: string }> }) {
  const { docId } = await params;
  return <ReportReviewPage docId={docId} />;
}
