import type { Metadata } from "next";
import { Suspense } from "react";
import { EmployeeDetail } from "@/features/accounts/payroll/EmployeesPages";

export const metadata: Metadata = { title: "Employee" };
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <EmployeeDetail id={id} />
    </Suspense>
  );
}
