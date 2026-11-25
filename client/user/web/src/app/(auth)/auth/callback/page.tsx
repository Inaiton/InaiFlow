import type { Metadata } from "next";
import { Suspense } from "react";
import { OAuthCallback } from "@/features/auth/components/OAuthCallback";


export const metadata: Metadata = { title: "Signing in" };

export default function Page() {
  return (
    <Suspense>
      <OAuthCallback />
    </Suspense>
  );
}
