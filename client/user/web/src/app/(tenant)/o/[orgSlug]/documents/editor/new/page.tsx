import { redirect } from "next/navigation";

/** Spec route alias → the 3-step wizard. */
export default async function Page({ params }: { params: Promise<{ orgSlug: string }> }) {
  const { orgSlug } = await params;
  redirect(`/o/${orgSlug}/documents/reports/new`);
}
