import type { Metadata } from "next";
import { Suspense } from "react";
import { EmployeesPage } from "@/features/accounts/payroll/EmployeesPages";

export const metadata: Metadata = { title: "Employees" };
export default function Page() {
  return (
    <Suspense>
      <EmployeesPage />
    </Suspense>
  );
}
