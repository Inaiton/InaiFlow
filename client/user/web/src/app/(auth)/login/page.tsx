import type { Metadata } from "next";
import { Suspense } from "react";
import { LoginForm } from "@/features/auth/components/LoginForm";
import { RedirectIfAuthenticated } from "@/core/auth/RequireAuth";

export const metadata: Metadata = { title: "Sign in" };

export default function Page() {
  return (
    <Suspense>
      <RedirectIfAuthenticated to="/"><LoginForm /></RedirectIfAuthenticated>
    </Suspense>
  );
}
