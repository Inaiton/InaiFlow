import type { Metadata } from "next";
import { Suspense } from "react";
import { DayBook } from "@/features/accounts/vouchers/DayBook";

export const metadata: Metadata = { title: "Day book" };
export default function Page() {
  return (
    <Suspense>
      <DayBook />
    </Suspense>
  );
}
