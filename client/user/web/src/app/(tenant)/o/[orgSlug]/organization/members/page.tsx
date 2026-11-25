import type { Metadata } from "next";
import { Suspense } from "react";
import { MembersPage } from "@/features/organization/components/MembersPage";

export const metadata: Metadata = { title: "Members" };
export default function Page() {
  return (
    <Suspense>
      <MembersPage />
    </Suspense>
  );
}
