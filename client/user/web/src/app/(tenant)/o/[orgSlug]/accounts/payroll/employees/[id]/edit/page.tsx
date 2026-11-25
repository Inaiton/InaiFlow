import type { Metadata } from "next";
import { Suspense } from "react";
import { EmployeeEditor } from "@/features/accounts/payroll/EmployeeEditor";

export const metadata: Metadata = { title: "Alter employee" };
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <EmployeeEditor id={id} />
    </Suspense>
  );
}
