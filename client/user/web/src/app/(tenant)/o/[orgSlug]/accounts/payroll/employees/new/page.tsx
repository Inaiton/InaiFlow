import type { Metadata } from "next";
import { Suspense } from "react";
import { EmployeeEditor } from "@/features/accounts/payroll/EmployeeEditor";

export const metadata: Metadata = { title: "New employee" };
export default function Page() {
  return (
    <Suspense>
      <EmployeeEditor />
    </Suspense>
  );
}
