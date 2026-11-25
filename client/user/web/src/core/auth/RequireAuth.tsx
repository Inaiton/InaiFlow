"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { FullScreenLoader } from "@/components/shell/FullScreenLoader";
import { useAuth } from "./AuthProvider";

/** Client-side route guard: loader while bootstrapping, redirect to /login?next=… when anonymous. */
export function RequireAuth({ children, allowImpersonation = true }: { children: ReactNode; allowImpersonation?: boolean }) {
  const { status, isImpersonating } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const blocked = !allowImpersonation && isImpersonating;
  useEffect(() => {
    if (status === "anonymous") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);
  if (status !== "authenticated") return <FullScreenLoader label={status === "loading" ? "Signing you in…" : "Redirecting to sign in…"} />;
  if (blocked) return <FullScreenLoader label="Personal space isn’t available during a support session." />;
  return <>{children}</>;
}

/** For /login, /signup…: send already-signed-in users onward (honours a safe `?next=`). Needs <Suspense>. */
export function RedirectIfAuthenticated({ to = "/", children }: { to?: string; children: ReactNode }) {
  const { status, isImpersonating } = useAuth();
  const router = useRouter();
  const target = safeNext(useSearchParams().get("next"), to);
  useEffect(() => {
    if (status === "authenticated" && !isImpersonating) router.replace(target);
  }, [status, isImpersonating, router, target]);
  if (status === "loading") return <FullScreenLoader label="Checking your session…" />;
  return <>{children}</>;
}

/** Only allow relative, same-app redirect targets (prevents open redirects via ?next=). */
export function safeNext(next: string | null | undefined, fallback = "/"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  return next;
}
