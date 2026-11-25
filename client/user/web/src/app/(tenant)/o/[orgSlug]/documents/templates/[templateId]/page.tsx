import type { Metadata } from "next";
import { TemplateBuilder } from "@/features/documents/components/templates/TemplateBuilder";

export const metadata: Metadata = { title: "Template builder" };
export default async function Page({ params }: { params: Promise<{ templateId: string }> }) {
  const { templateId } = await params;
  return <TemplateBuilder templateId={templateId} />;
}
