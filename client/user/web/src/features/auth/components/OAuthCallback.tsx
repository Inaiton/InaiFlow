"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/core/auth/AuthProvider";
import { safeNext } from "@/core/auth/RequireAuth";
import { Hint } from "@/components/ui/feedback";
import { AuthCard } from "@/components/shell/AuthShell";
import { FullScreenLoader } from "@/components/shell/FullScreenLoader";

/** Google OAuth return: the server set the refresh cookie; AuthProvider's bootstrap refresh picks it up. */
export function OAuthCallback() {
  const params = useSearchParams();
  const { status } = useAuth();
  const router = useRouter();
  const failed = params.get("error");
  const next = safeNext(params.get("next"));
  useEffect(() => {
    if (!failed && status === "authenticated") router.replace(next);
  }, [failed, status, router, next]);
  if (!failed && status !== "anonymous") return <FullScreenLoader label="Finishing Google sign-in…" />;
  return (
    <AuthCard title="Google sign-in didn’t complete" footer={<Link href="/login">Back to sign in</Link>}>
      <Hint tone="danger">{failed === "access_denied" ? "You cancelled the Google prompt." : "We couldn’t sign you in with Google. Try again or use your email and password."}</Hint>
    </AuthCard>
  );
}
