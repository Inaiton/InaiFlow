import type { Metadata } from "next";
import { NcrDetail } from "@/features/operations/components/iso/NcrDetail";

export const metadata: Metadata = { title: "NCR" };
export default async function Page({ params }: { params: Promise<{ ncrId: string }> }) {
  const { ncrId } = await params;
  return <NcrDetail ncrId={ncrId} />;
}
