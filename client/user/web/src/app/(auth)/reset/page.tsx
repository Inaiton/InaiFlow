import type { Metadata } from "next";
import { Suspense } from "react";
import { ResetForm } from "@/features/auth/components/PasswordResetForms";


export const metadata: Metadata = { title: "Choose a new password" };

export default function Page() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
