import type { Metadata } from "next";
import { Suspense } from "react";
import { AclPage } from "@/features/organization/components/AclPage";

export const metadata: Metadata = { title: "Record overrides" };
export default function Page() {
  return (
    <Suspense>
      <AclPage />
    </Suspense>
  );
}
