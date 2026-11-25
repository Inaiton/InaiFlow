import type { Metadata } from "next";
import { Suspense } from "react";
import { GroupsPage } from "@/features/accounts/masters/GroupsPage";

export const metadata: Metadata = { title: "Groups" };
export default function Page() {
  return (
    <Suspense>
      <GroupsPage />
    </Suspense>
  );
}
