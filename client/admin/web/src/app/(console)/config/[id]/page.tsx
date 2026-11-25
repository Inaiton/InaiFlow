import { ConfigEditorPage } from "@/features/config/ConfigEditorPage";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ConfigEditorPage id={id} />;
}
