import type { Metadata } from "next";
import { Suspense } from "react";
import { RolesPage } from "@/features/organization/components/RolesPage";

export const metadata: Metadata = { title: "Roles & access" };
export default function Page() {
  return (
    <Suspense>
      <RolesPage />
    </Suspense>
  );
}
