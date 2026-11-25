import type { Metadata } from "next";
import { Suspense } from "react";
import { ImpersonateLanding } from "@/features/auth/components/ImpersonateLanding";


export const metadata: Metadata = { title: "Support session" };

export default function Page() {
  return (
    <Suspense>
      <ImpersonateLanding />
    </Suspense>
  );
}
