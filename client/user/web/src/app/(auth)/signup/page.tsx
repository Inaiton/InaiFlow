import type { Metadata } from "next";
import { Suspense } from "react";
import { SignupForm } from "@/features/auth/components/SignupForm";
import { RedirectIfAuthenticated } from "@/core/auth/RequireAuth";

export const metadata: Metadata = { title: "Create account" };

export default function Page() {
  return (
    <Suspense>
      <RedirectIfAuthenticated to="/"><SignupForm /></RedirectIfAuthenticated>
    </Suspense>
  );
}
