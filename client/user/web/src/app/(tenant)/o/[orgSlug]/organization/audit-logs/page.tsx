import type { Metadata } from "next";
import { Suspense } from "react";
import { AuditLogPage } from "@/features/organization/components/AuditLogPage";

export const metadata: Metadata = { title: "Audit log" };
export default function Page() {
  return (
    <Suspense>
      <AuditLogPage />
    </Suspense>
  );
}
