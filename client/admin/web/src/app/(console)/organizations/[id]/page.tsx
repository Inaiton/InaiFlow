import { OrgDetailPage } from "@/features/organizations/OrgDetailPage";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OrgDetailPage id={id} />;
}
