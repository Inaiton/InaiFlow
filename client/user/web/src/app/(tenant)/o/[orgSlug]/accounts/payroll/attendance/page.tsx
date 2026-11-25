import type { Metadata } from "next";
import { Suspense } from "react";
import { AttendancePage } from "@/features/accounts/payroll/AttendancePage";

export const metadata: Metadata = { title: "Attendance" };
export default function Page() {
  return (
    <Suspense>
      <AttendancePage />
    </Suspense>
  );
}
