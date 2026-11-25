import type { Metadata } from "next";
import { ReportEditorPage } from "@/features/documents/components/reports/ReportEditorPage";

export const metadata: Metadata = { title: "Fill in the results" };
export default async function Page({ params }: { params: Promise<{ docId: string }> }) {
  const { docId } = await params;
  return <ReportEditorPage docId={docId} />;
}
