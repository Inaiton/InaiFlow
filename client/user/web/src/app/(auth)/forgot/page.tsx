import type { Metadata } from "next";
import { Suspense } from "react";
import { ForgotForm } from "@/features/auth/components/PasswordResetForms";


export const metadata: Metadata = { title: "Reset password" };

export default function Page() {
  return (
    <Suspense>
      <ForgotForm />
    </Suspense>
  );
}
