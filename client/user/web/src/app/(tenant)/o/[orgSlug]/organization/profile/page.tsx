import type { Metadata } from "next";
import { Suspense } from "react";
import { OrgProfilePage } from "@/features/organization/components/OrgProfilePage";

export const metadata: Metadata = { title: "Organization profile" };
export default function Page() {
  return (
    <Suspense>
      <OrgProfilePage />
    </Suspense>
  );
}
